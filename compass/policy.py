"""Narrow, source-grounded release guards. No model calls or retrieval loops."""
import json
import re
from decimal import Decimal
from pathlib import Path

CATEGORY_SPANS = json.loads(Path(__file__).with_name('policy_categories.json').read_text(encoding='utf-8'))
SCOPE_NOTE = ('This local knowledge base covers approved undergraduate sections. '
              'Postgraduate-only requirements are outside its indexed coverage; this does not mean they are absent from the original PDFs.')

def normalize(text):
    return ' '.join(text.split())


AI_REFERENCE_INTENT = r'\b(?:cit(?:e|es|ed|ing|ation|ations)|referenc(?:e|es|ed|ing)|quot(?:e|es|ed|ing|ation|ations)|attribut(?:e|es|ed|ing|ion|ions))\b'


def ai_reference_topic(question):
    # Asking us to quote a policy is not itself AI-content referencing.
    topic=re.sub(r'^\s*(?:please\s+)?(?:(?:can|could|would|will)\s+you\s+(?:please\s+)?)?(?:quote|cite)\b','',question,flags=re.I)
    topic=re.sub(r'\b(?:cite|reference)\s+(?:(?:the|your|each|every|all)\s+)?(?:sources?|rules?|polic(?:y|ies)|answers?|points?|claims?|evidence)\b','',topic,flags=re.I)
    return re.sub(r'\b(?:with|include|provide|show|give)\s+(?:(?:source|proper|clear)\s+)?citations?\b','',topic,flags=re.I)


def ai_reference_intent(question):
    topic=ai_reference_topic(question)
    prompt_evidence=re.search(r'\bprompts?\b',topic,re.I) and re.search(r'\b(?:images?|screenshots?|evidence)\b',topic,re.I)
    return bool(re.search(AI_REFERENCE_INTENT,topic,re.I) or prompt_evidence)


def ai_preparation_only(question):
    scope=re.sub(r'\b(?:not|no|without)\s+(?:any\s+)?(?:incorporat\w*\s+)?(?:submitted|quoted|embedded|verbatim|incorporated)\s+(?:content|text|work|images?|figures?|quotations?)\b','',question,flags=re.I)
    return bool(re.search(r'prepar|research',question,re.I)
                and re.search(r'\b(?:solely|only|purely|just)\b',question,re.I)
                and not re.search(r'\b(?:submitted|quot\w*|embedded|images?|figures?|incorporat\w*|verbatim)\b',scope,re.I))

def parse_rewrite(raw):
    try:
        obj = json.loads(raw)
    except (ValueError, TypeError):
        raise ValueError('The response could not be validated: question interpretation was malformed. Your question is saved; retry or state the topic explicitly.') from None
    if (not isinstance(obj, dict) or set(obj) != {'question', 'unresolved'}
        or type(obj['unresolved']) is not bool or not isinstance(obj['question'], str)
        or not obj['question'].strip() or len(obj['question']) > 6000):
        raise ValueError('The response could not be validated: question interpretation was malformed. Your question is saved; retry or state the topic explicitly.')
    return {'question': obj['question'].strip(), 'unresolved': obj['unresolved']}

def is_ambiguous_fee(question):
    return bool(re.fullmatch(r'\s*(?:what(?: is|\x27s| are)|how much is) (?:the |its |that )?(?:fee|fees|charge|cost)\s*[?.!]*\s*', question, re.I))

def external_transfer(question):
    return bool(re.search(r'\b(?:transfer\w*|exempt\w*)\b', question, re.I)
                and re.search(r'\b(?:another|other|previous|different|external)[ -]+(?:university|institution)|\bexternal[ -]+applicants?\b|\bapplicants?\b.{0,35}\boutside FAST\b', question, re.I))

POSTGRAD_SCOPE = r'\b(?:master[’\x27]?s?|(?-i:MS)(?!\.|\s+(?:office|word|excel|teams)\b)|m\.s\.?|ms(?=\s+(?:students?|programs?|degrees?|studies|funding|sponsorships?)\b)|Ph\.?D\.?|doctoral|postgraduate|graduate[- ]only|graduate(?=\s+(?:students?|programs?|degrees?|studies|level|funding|sponsorships?|scholarships?|rules?|requirements?)))\b'

def postgraduate_scope(question):
    return bool(re.search(POSTGRAD_SCOPE,question,re.I))


def mixed_degree(question):
    # A request not to substitute a bachelor limit does not request that limit.
    positive=re.sub(r'\b(?:do not|don.t|without)\s+(?:substitut\w*|us\w*)\b[^?;.]*','',question,flags=re.I)
    # An undergraduate rule used as a proposed basis for a postgraduate answer
    # is a premise, not a separately requested undergraduate subject. Preserve
    # other explicit undergraduate clauses outside that bounded basis phrase.
    positive=re.sub(r'\b(?:use|using|given|from|based(?: only)? on)\s+'
                    r'(?:(?:the|these|those|this|that|only|documented|indexed|available|existing)\s+)*'
                    r'(?:undergraduates?|bachelor(?:s|[’\x27]s)?|BS)\b'
                    r'(?:(?!\band\b)[^;?.]){0,50}?\b(?:rules?|allowances?|sponsorships?|funding|limits?)\b',
                    '',positive,flags=re.I)
    return bool(re.search(r'\b(?:undergraduates?|bachelor\w*|BS)\b',positive,re.I)
                and postgraduate_scope(question))

def undergraduate_part(question):
    # Preserve an explicit supported first clause instead of replacing its
    # excluded second subject with another undergraduate subject.
    clauses=re.split(r',?\s+and\s+',question,flags=re.I)
    supported=[part for part in clauses if not postgraduate_scope(part)]
    excluded=[part for part in clauses if postgraduate_scope(part)]
    separate_requests=all(re.match(r'\s*(?:(?:can|could|would|will)\s+(?:you\s+)?)?(?:infer|derive|deduce|extrapolate|establish|use|whether|explain|give|tell|provide|state|what|how|who|whom)\b',part,re.I) for part in excluded)
    if len(clauses)>1 and supported and excluded and separate_requests:
        return ' and '.join(supported).rstrip(' ,;.?')+'?'
    comparison=re.match(r'\s*compare\s+(.+?)\s+(?:with|versus)\s+(.+)',question,re.I)
    if comparison and not postgraduate_scope(comparison[1]) and postgraduate_scope(comparison[2]):
        return 'Explain the documented '+comparison[1].rstrip(' .?')+' rules.'
    return re.sub(POSTGRAD_SCOPE, 'undergraduate', question, flags=re.I)

def partial_sponsorship_reply(question,sources):
    """Complete only the supported sponsorship part from actual packed rules."""
    if not re.search(r'\bsponsorships?\b',question,re.I) or re.search(r'contact|email|who|whom|\b(?:gym|library|CGPA)\b',question,re.I):return None
    for sid,source in sources.items():
        text=normalize(source['excerpt'])
        match=re.search(r'Rules for Internal Sponsorships:?\s*(.*?)(?=B\. External Sponsorships|$)',text,re.I)
        if match and re.search(r'Bachelors:\s*8 semesters',match[1],re.I) and re.search(r'tuition\s*fee only',match[1],re.I):
            return ('The indexed undergraduate internal sponsorship rules state:\n\n> '+match[1].strip()+f' [{sid}]','partial_undergraduate_sponsorship')
    return None

def categories(source):
    result={s['category'] for s in CATEGORY_SPANS.get(source.get('chunk_id'), [])}
    text=source['excerpt']
    if re.search(r'This scholarship is for|Merit Scholarships? for Bachelor',text,re.I):result.add('scholarship')
    if re.search(r'position medals?|7\.11',text,re.I):result.add('medal')
    return result

def theory_cases(question):
    q=normalize(question)
    if not re.search(r'\brepeat|retake',q,re.I):return []
    # A corrected premise replaces the earlier one; history is resolved upstream.
    q=re.split(r'\bcorrection\s*:',q,flags=re.I)[-1]
    gap=r'(?:(?!\btheory\b)[^.;?!]){0,100}?'
    outcomes=[('4.8',r'pass(?:ed|es|ing)? (?:the )?theory'+gap+r'fail(?:ed|s|ing)? (?:in )?(?:its associated |the |associated )?lab'),
              ('4.7',r'fail(?:ed|s|ing)? (?:in )?(?:the )?theory'+gap+r'pass(?:ed|es|ing)? (?:its associated |the |associated )?lab'),
              ('4.8',r'theory (?:was )?passed'+gap+r'lab (?:was )?failed'),
              ('4.7',r'theory (?:was )?failed'+gap+r'lab (?:was )?passed')]
    matches=sorted((m.start(),rule) for rule,pattern in outcomes for m in re.finditer(pattern,q,re.I))
    return list(dict.fromkeys(rule for _,rule in matches))

def theory_case(question):
    cases=theory_cases(question)
    return cases[0] if cases else None

FACETS={
    'graduation_cgpa': (r'\bgraduat\w*\b.*?\bCGPA(?![A-Za-z_])|\bCGPA(?![A-Za-z_]).*?\bgraduat\w*\b', 'Minimum CGPA required for bachelor degree graduation.', r'1\.25\s+(.*?required for graduation\.)'),
    'gym_registration': (r'gym.*?registration|registration.*?gym', 'Hostel gym one-time registration fee.', r'(Students may avail the hostel gym facility.*?one-time registration fee of Rs\.\s*[\d,]+\.)'),
    'financial_contact': (r'financial[ -]assistance', 'CFD Financial Assistance office contact email telephone extension Ms Nooria Fatima.', r'(FINANCIAL ASSISTANCE.*?@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\s+Ext:\s*\d+)'),
    'library_contact': (r'\blibrary\b', 'CFD library librarian contact email telephone extension Azhar Mehmood.', r'(LIBRARY.*?@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\s+Ext:\s*\d+)'),
    'accounts_contact': (r'\baccounts\b', 'CFD Accounts Office contact email telephone extension.', r'(ACCOUNTS OFFICE.*?@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\s+Ext:\s*\d+)'),
}

def requested_facets(question):
    contact_intent=bool(re.search(r'\bcontacts?|emails?|extensions?\b|\bwho\s+(?:manages|handles|coordinates)\b',question,re.I))
    found=[(re.search(pattern,question,re.I).start(),name) for name,(pattern,_,_) in FACETS.items()
           if re.search(pattern,question,re.I) and (not name.endswith('_contact') or contact_intent)]
    library_rules=re.search(r'\b(?:borrow\w*|books?|renew\w*|overdue|fines?)\b',question,re.I)
    library_contact=re.search(r'\blibrary(?:[’\x27]s)?\s+(?:(?:office|librarian|staff|support|contact)\s+)?(?:contacts?|emails?|extensions?)\b|\b(?:contacts?|emails?|extensions?)(?:\s+(?:address|details|number))?\s+(?:of|for|at)\s+(?:the\s+)?library\b|\blibrary\s+and\s+(?:Accounts|Financial Assistance)\s+(?:contacts?|emails?|extensions?)\b',question,re.I)
    if library_rules and not library_contact:
        found=[item for item in found if item[1]!='library_contact']
    return [name for _,name in sorted(found)]

def generic_assistance_contact(question):
    return bool(re.search(r'\bassistance\b',question,re.I)
                and re.search(r'contact|email|extension|whom.{0,25}(?:ask|approach)',question,re.I)
                and not re.search(r'\b(?:financial|academic|technical|medical|hostel|library|IT|all|every|directory|offices)\b',question,re.I))

def explicit_multipart(question):
    references=re.sub(r'\bin that order\b','',question,flags=re.I)
    return len(requested_facets(question))>1 and not re.search(r'\b(?:it|that|those|she|he|original|previous)\b',references,re.I)

def evidence_facets(question,sources):
    return {name:[sid for sid,s in sources.items() if re.search(FACETS[name][2],normalize(s['excerpt']),re.I)] for name in requested_facets(question)}

def facet_chunk_ids(name):
    return [cid for cid,spans in CATEGORY_SPANS.items() if any(s['category']=='facet:'+name for s in spans)]

def exhaustive_admissions(question):
    return bool(re.search(r'admission',question,re.I) and (
        re.search(r'\bevery\b|\ball\b|complete|comprehensive',question,re.I)
        or re.search(r'indexed|selected|covered',question,re.I) and re.search(r'scope|exclud|coverage|boundar',question,re.I)))

ADMISSIONS_NOTE=('This index covers selected undergraduate readmission, degree-change and admission-closure rules, '
                 'not every admission policy in the four original PDFs. External-applicant admission and credit-transfer procedures are excluded.\n\n')

def check_administrative_claims(text):
    if re.search(r'(?<!closure of )\bAdmission results in (?:the )?termination',text,re.I):
        raise ValueError('The response could not be validated: admission was confused with closure of admission.')
    if re.search(r'warning.{0,60}(?:does not remain|removed|erased|deleted).{0,30}record',text,re.I):
        raise ValueError('The response could not be validated: resetting the warning count does not establish deletion of historical records.')
    for claim in re.finditer(r'(?:Academic Office|University) has not changed',text,re.I):
        prefix=text[max(0,claim.start()-120):claim.start()]
        negated=re.search(
            r'\b(?:(?:without|not)\s+(?:claiming|asserting|confirming|establishing|verifying)'
            r'|(?:cannot|can not|can.t|do not|does not)\s+(?:claim|assert|confirm|establish|verify))'
            r'\s+(?:that\s+)?(?:the\s+)?$',prefix,re.I)
        if not negated:
            raise ValueError('The response could not be validated: static documents cannot verify whether a recent announcement occurred.')
    return text

def merit_gpa_reply(question, sources):
    """Compare supplied GPAs only with the retrieved merit/internal rules."""
    if not re.search(r'merit[- ]scholarship',question,re.I) or re.search(r'\bloans?\b',question,re.I):return None
    if requested_facets(question) or re.search(r'\b(?:rooms?|hostels?|accommodation)\b',question,re.I):return None  # Preserve other explicitly requested subjects for the ordinary answer chain.
    def grade(label):
        number=r'([0-4](?:\.\d+)?)(?!\d|\.\d)'
        matches=re.findall(label+r'\s*(?:(?:is|of|equals|exactly|=)\s*)*'+number,question,re.I)
        matches+=re.findall(r'(?<![\d.])'+number+r'\s*'+label,question,re.I)
        values={Decimal(x) for x in matches}
        return next(iter(values)) if len(values)==1 else None
    semester=grade(r'(?:semester[- ]GPA|SGPA)')
    cumulative=grade(r'(?:cumulative[- ]GPA|CGPA)')
    if semester is None or cumulative is None:return None
    merit=None;internal=None;warning=None
    for sid,source in sources.items():
        t=normalize(source['excerpt'])
        m=re.search(r'Continuation of merit scholar\s*ship is subject to maintaining semester GPA of ([\d.]+) or higher\.',t,re.I)
        if m:merit=(sid,m.group(),Decimal(m.group(1)))
        m=re.search(r'It is suspended if the student.s CGPA falls below the minimum specified to avoid warning and shall be restored upon getting out of warning by improvement in CGPA\.',t,re.I)
        if m:internal=(sid,m.group())
        m=re.search(r'Minimum CGPA required to avoid aca\s*demic warning is ([\d. ]+?) for all undergraduate programs\.',t,re.I)
        if m:warning=(sid,m.group(),Decimal(m.group(1).replace(' ','')))
    if not merit:return None
    met='meets' if semester>=merit[2] else 'does not meet'
    text=f'The supplied semester GPA of {semester} {met} the merit-scholarship semester-GPA condition of {merit[2]} or higher [{merit[0]}].'
    narrow=bool(re.search(r'(?:semester[- ]GPA|SGPA)[- ]condition',question,re.I))
    if not narrow:
        if not internal or not warning:
            return (text+' The retrieved passages do not establish all evidence needed to apply the cumulative-GPA sponsorship condition. These numbers alone cannot confirm continued funding.','incomplete_merit_gpa_evidence')
        relation='below' if cumulative<warning[2] else 'not below'
        text+=f' The supplied CGPA of {cumulative} is {relation} the undergraduate warning threshold of {warning[2]} [{warning[0]}].'
        text+='\n\nThe applicable internal-scholarship rule states:\n\n> '+internal[1]+f' [{internal[0]}]'
        text+=('\n\nTherefore the stated CGPA meets the documented suspension condition; the semester GPA alone does not guarantee continuation.' if cumulative<warning[2] else '\n\nThis CGPA does not meet that below-threshold suspension condition; it does not establish that every other scholarship condition is met or guarantee continuation.')
    return text+' This compares supplied numbers with documented conditions, not a verified university record or award decision.','merit_gpa_conditions'

def merit_continuation_reply(question, sources):
    """Keep merit-only and category-wide clauses separate in a broad answer.

    Compose only complete, actually retrieved rule spans. Other policy subjects
    continue through the ordinary answer chain and its completeness checks.
    """
    if not (re.search(r'merit[- ]scholarship',question,re.I)
            and re.search(r'continu|renew|retain|keep|conditions?|requirements?|semester[- ]GPA|SGPA',question,re.I)):return None
    facets=requested_facets(question)
    if any(f!='financial_contact' for f in facets):return None
    if re.search(r'contact|email|extension|\bwho\b|\bwhom\b',question,re.I) and 'financial_contact' not in facets:return None
    if re.search(r'repay|interest|installment|application|\bapply\s+for\b|withdrawal|\bwithdraw\b|FYP|library|gym|hostel|Dean|Rector|readmission',question,re.I):return None
    if re.search(r'medal',question,re.I) and not re.search(r'rather than[^.;?]*medal',question,re.I):return None
    rules={}
    for sid,source in sources.items():
        text=normalize(source['excerpt'])
        patterns={
            'semester':r'Continuation of merit scholar\s*ship (?:is subject to maintaining|requires) semester GPA of [\d.]+ or higher\.',
            'warning':r'Minimum CGPA required to avoid aca\s*demic warning is [\d. ]+? for all undergraduate programs\.',
            'internal':r'Rules for Internal (?:Scholarships|Sponsorships):?\s*(.*?)(?=(?:B\.\s*)?External (?:Scholarships|Sponsorships)|$)',
            'summer':r'Financial assistance, s\s*cholarship or fee concession is not available in summer semester\.',
            'contact':FACETS['financial_contact'][2],
        }
        if re.search(r'This scholarship is for|Merit Scholarships? for Bachelor',text,re.I):
            patterns.update({
                'duration':r'This scholarship is for .*?full tuition fee\.',
                'load':r'A student registering for less or more credit hours.*?eligible for Merit Scholarship\.',
                'status':r'Student must not have failed, repeated or withdrawn from a course in that semester\.?',
            })
        for key,pattern in patterns.items():
            match=re.search(pattern,text,re.I)
            if not match or key in rules:continue
            value=match[1] if key in ('internal','contact') else match[0]
            if key=='internal' and not (re.search(r'Bachelors:?\s*8 semesters',value,re.I) and 'CGPA' in value and 'restored' in value and re.search(r'tuition\s*fee only',value,re.I)):continue
            rules[key]=(value.strip(),sid)
    required=['semester','duration','load','status','internal','warning']
    if re.search(r'summer',question,re.I):required.append('summer')
    if 'financial_contact' in facets:required.append('contact')
    if any(key not in rules for key in required):return None
    quote=lambda key:'> '+rules[key][0]+f' [{rules[key][1]}]'
    parts=['**Merit-scholarship semester-GPA continuation rule:**\n\n'+quote('semester'),
           '**Scholarship-specific course and study conditions:**\n\n'+'\n\n'.join(quote(key) for key in ('duration','load','status')),
           '**Internal-sponsorship conditions:**\n\n'+quote('internal'),
           '**Undergraduate warning threshold:**\n\n'+quote('warning')]
    if 'summer' in required:parts.append('**Summer semester:**\n\n'+quote('summer'))
    if 'contact' in required:parts.append('**Printed Financial Assistance contact:**\n\n'+quote('contact'))
    if re.search(r'guarantee|only rule|by itself|alone',question,re.I):parts.insert(0,'Meeting one condition alone does not establish that all the other conditions are met or verify a personal award decision.')
    if re.search(r'(?:confirm\w*|verif\w*|establish\w*|prov\w*)[^?;.!]*(?:my|personal|individual)[^?;.!]*(?:award|scholarship)|(?:my|personal|individual)[^?;.!]*award[^?;.!]*(?:confirm\w*|verif\w*)',question,re.I):parts.insert(0,'I cannot confirm a personal scholarship award from policy documents; these passages describe conditions, not an individual university award record.')
    if re.search(r'loans?|every internal|all internal',question,re.I):parts.append('The quoted semester-GPA sentence names merit scholarships. These passages do not establish the same semester-GPA requirement for every internal funding scheme or study loan.')
    return '\n\n'.join(parts),'merit_continuation_source_rules'


def hostel_room_reply(question, sources):
    """Keep the documented room rule when a private assignment is unknowable."""
    if not (re.search(r'\brooms?\b',question,re.I)
            and re.search(r'allocat|eligib|single|double',question,re.I)
            and re.search(r'document|conditions?|rules?|policy|eligib',question,re.I)):return None
    # Other requested subjects/contact details belong in the ordinary full chain.
    if requested_facets(question) or re.search(r'\b(?:contact|email|who|whom|scholarships?|sponsorships?|loans?|withdraw|library|gym|cooler|FYP|tuition)\b',question,re.I):return None
    for sid,source in sources.items():
        t=normalize(source['excerpt'])
        rule=re.search(r'As per policy, single- and double-occupancy rooms.*?The new batch will be accommodated in shared rooms\.',t,re.I)
        if rule and all(term in rule.group() for term in ('top CGPAs','valid medical reasons','Medical Officer','Hall Management Committee','competent authority')):
            prefix='I cannot determine a personal room assignment or confirm eligibility for a particular student. The indexed guidebook states:'
            return prefix+'\n\n> '+rule.group()+f' [{sid}]','hostel_room_policy'
    return None

def policy_wording_reply(question, sources):
    """Quote two observed rule families without adding converse/mandatory terms."""
    if requested_facets(question) or re.search(r'\b(?:rooms?|hostels?|gym|library|contacts?|email|merit[- ]scholarship)\b',question,re.I):return None
    if re.search(r're[- ]?check',question,re.I) and re.search(r'refund|fee.{0,30}(?:back|return)',question,re.I):
        procedural=re.search(r'\bapply\b|applications?|procedure|how soon|how quickly|payment|\bfree\b',question,re.I)
        other_topic=re.search(r'\b(?:retake|withdraw\w*|scholarship|warning|attendance|FYP|lab)\b',question,re.I)
        if procedural and not other_topic:
            rules={}
            for sid,source in sources.items():
                passage=normalize(source['excerpt'])
                for number in ('5.20','5.21','5.25'):
                    match=re.search(re.escape(number)+r'\s+(.*?)(?=5\.\d+\s|$)',passage,re.I)
                    if match:rules[number]=(match[1].strip(),sid)
            if (all(number in rules for number in ('5.20','5.21','5.25'))
                and 'prescribed form together with rechecking fee' in rules['5.20'][0]
                and re.search(r'should r\s*each.*seven days',rules['5.21'][0],re.I)
                and re.search(r'refunded if.*in\s*crease in marks',rules['5.25'][0],re.I)):
                text='The indexed rechecking application and refund rules state:\n\n'+'\n\n'.join(
                    '> '+rules[number][0]+f' [{rules[number][1]}]' for number in ('5.20','5.21','5.25'))
                if re.search(r'no.{0,20}(?:increas|marks)|not.{0,20}increas|same|unchang|decreas|lower|only if|clause|sentence',question,re.I):
                    text+='\n\nThe refund clause uses “if”, not “only if”; it does not explicitly settle the unchanged or decreased-marks outcome. Confirm that application with the Examination Office.'
                return text,'rechecking_procedure_wording'
        if re.search(r'procedure|steps|form|deadline|days|viewing|amount|how much|cost|how soon|how quickly|\bapply\b|application|payment|\bfree\b',question,re.I):return None
        for sid,source in sources.items():
            m=re.search(r'Rechecking fee will be refunded if there is an in\s*crease in marks\.',normalize(source['excerpt']),re.I)
            if m:
                text='The specific rechecking clause states:\n\n> '+m.group()+f' [{sid}]'
                if re.search(r'no.{0,20}(?:increas|marks)|not.{0,20}increas|same|unchang|decreas|lower|only if|clause|sentence',question,re.I):
                    text+='\n\nThis clause uses “if”, not “only if”, and does not explicitly describe the no-increase or decreased-marks outcome. I cannot confirm a refund or no-refund outcome from this clause alone; confirm its application with the Examination Office.'
                return text,'rechecking_refund_wording'
    aid_wording=(re.search(r'\b(?:form|application)\b',question,re.I) and re.search(r'word|quote|literal|sentence|line|recommend|preserv|should apply|must apply',question,re.I))
    award_proof=re.search(r'eligib',question,re.I) and re.search(r'award|proof',question,re.I)
    if (re.search(r'financial[- ]aid|financial[- ]assistance|\bassistance\b',question,re.I)
        and (aid_wording or award_proof)
        and not re.search(r're[- ]?check|\bscholarship',question,re.I)):
        for sid,source in sources.items():
            m=re.search(r'All those who are admitted and are in real need of financial assistance should apply on the prescribed Financial Aid form\.',normalize(source['excerpt']),re.I)
            if m:
                prefix=('Eligibility to apply is not confirmation of an award; I cannot verify a personal award decision. ' if re.search(r'award|proof',question,re.I) else '')
                return prefix+'The indexed application wording is:\n\n> '+m.group()+f' [{sid}]','aid_application_wording'
    return None

WARNING_APPROVAL = r'Students on 2\s*nd academic warning must NOT register for a new course, unl\s*ess recommended by the HoD and approved by Controller of Examinations\.'

def summer_enrollment_reply(question, sources):
    """Keep this narrow summer comparison within its actual semester rules."""
    if not (re.search(r'\bsummer\b',question,re.I)
            and re.search(r'enrol\w*|(?:minimum|ten|10).{0,35}students?|minimum.{0,15}(?:course )?registration numbers?',question,re.I)):
        return None
    if re.search(r'withdraw|financial|scholarship|FYP|contact|email|regular|maximum|repeat|new course|duration',question,re.I):return None
    enrollment=None;attendance=None
    for sid,source in sources.items():
        passage=normalize(source['excerpt'])
        match=re.search(r'A minimum of TEN\s*\(10\) students should register in a summer course\. Otherwise, the course shall be dropped\.',passage,re.I)
        if match:enrollment=match[0]+f' [{sid}]'
        match=re.search(r'80% attendance rule shall apply to summer courses/labs\.',passage,re.I)
        if match:attendance=match[0]+f' [{sid}]'
    needs_attendance=bool(re.search(r'attendance',question,re.I))
    if enrollment and (attendance or not needs_attendance):
        parts=[enrollment]+([attendance] if needs_attendance else [])
        return 'The indexed summer rules state:\n\n'+'\n\n'.join('> '+p for p in parts),'summer_enrollment_wording'
    return None

def second_warning_reply(question, sources):
    second = re.search(r'\b(?:second|2nd|two)\b.{0,25}warnings?|warning\s*count\s*(?:of\s*)?2\b|\b2\s+academic warnings?', question, re.I)
    if not (second and re.search(r'new[ -]course', question, re.I)):
        return None
    if re.search(r'\b(?:first|third|contact|email|theory|lab|withdraw\w*|FYP|scholarship)\b|not (?:on|under)|no longer', question, re.I):
        return None
    for sid, source in sources.items():
        rule = re.search(WARNING_APPROVAL, normalize(source['excerpt']), re.I)
        if rule:
            return ('New-course registration is conditional, not automatic:\n\n> '+rule.group()+f' [{sid}]', 'second_warning_new_course')
    return ('I could not find this information in the provided documents.', 'required_warning_rule_missing')

def fyp_deficiency_reply(question, sources):
    broad=bool(re.search(r'\b(?:normal|requirements|prerequisites|eligibility|complete|full)\b',question,re.I))
    deficiency_permission=(re.search(r'deficien|missing.{0,12}courses?',question,re.I)
                           and re.search(r'warning',question,re.I)
                           and re.search(r'HoD|Director|permission|clause|waiv',question,re.I))
    if not ((re.search(r'\bfyp\s*-?\s*i\b',question,re.I) and (broad or re.search(r'deficien|missing|warning',question,re.I))) or deficiency_permission):
        return None
    if (requested_facets(question) or re.search(r'\bfyp\s*-?\s*ii\b|\b(?:theory|lab|gym|cooler|scholarship|withdraw\w*|contact|email)\b',question,re.I)):
        return None
    if broad:
        beginning=None;continuation=None
        for sid,source in sources.items():
            passage=normalize(source['excerpt'])
            start=re.search(r'4\.10\s+(.*?4\.11.*)$',passage,re.I)
            tail=re.search(r'^(and his warning count.*?)(?=Suspension of Registration|4\.16)',passage,re.I)
            if start and 'passed all courses' in start[1]:beginning=(sid,start[1])
            if tail and all(term in tail[1] for term in ('subsequent semester','one course','two courses','4.15')):continuation=(sid,tail[1])
        if beginning and continuation:
            return ('The indexed normal-registration and deficiency rules state (continuing across two PDF pages):\n\n> '
                    +beginning[1]+' '+continuation[1]+f' [{beginning[0]}] [{continuation[0]}]', 'fyp_normal_registration_rules')
        return ('I could not retrieve all normal FYP-I registration requirements from the provided passages.','required_fyp_normal_rules_missing')
    zero=[];rules=[]
    for sid,source in sources.items():
        passage=normalize(source['excerpt'])
        m=re.search(r'warning count must be zero to register for\s+FYP\s*-\s*I\.',passage,re.I)
        if m and not zero:zero=[m.group()+f' [{sid}]']
        for pattern in [r'4\.13\s+(The Head of department can allow registration in FYP-I where there is a deficiency of one course\.)',
                        r'4\.14\s+(The Director of the campus can allow registration in F\s*YP-I where there is deficiency of two courses\.)']:
            m=re.search(pattern,passage,re.I)
            if m and not any(m.group(1).strip() in rule for rule in rules):rules.append(m.group(1).strip()+f' [{sid}]')
    if not zero or not rules:
        return ('I could not find this information in the provided documents.','required_fyp_rule_missing')
    return ('The retrieved rules require a zero warning count for FYP-I. The course-deficiency permissions do not establish permission to waive that condition. They are discretionary, not automatic:\n\n'+ '\n\n'.join('> '+rule for rule in zero+rules),'fyp_deficiency_conditions')

def disciplinary_reply(question,sources):
    """Expose conflicting retrieved wording, without deciding policy precedence."""
    if not re.search(r'cheat|dishonest|unfair means|\bDDC\b|\bCDC\b|disciplinary.{0,20}(?:penalt|punish)',question,re.I):return None
    if re.search(r'scholarship|approv|Rector|honou?r',question,re.I) and not re.search(r'minimum|maximum|penalt|punish|consequen|what happens',question,re.I):return None
    ddc=bool(re.search(r'\bDDC\b|department.{0,20}(?:committee|disciplin)',question,re.I))
    cdc=bool(re.search(r'\bCDC\b|campus.{0,20}(?:committee|disciplin)',question,re.I))
    broad=not ddc and not cdc
    patterns={
        'general':r'(The minimum punishment for using unfair means is.*?final examination\.)',
        'exam':r'(Any evidence of cheating will earn you.*?minimum penalty\.)',
        'ddc_handbook':r'(If the course instructor refers.*?minimum punishment.*?grade in that course\.)',
        'ddc_academic':r'8\.15\s+(.*?)(?=8\.16\b|$)',
        'cdc_handbook':r'(If the Head of Department refers.*?The CDC may recommend.*?university\.)',
        'cdc_academic':r'8\.16\s+(.*?)(?=8\.17\b|$)',
        'rector':r'(All disciplinary Committee recommendations.*?approved by the Rector\.)',
        'extreme':r'8\.17\s+(.*?)(?=8\.18\b|$)',
        'honors':r'8\.18\s+(.*?)(?=8\.19\b|$)',
    }
    found={}
    for name,pattern in patterns.items():
        for sid,source in sources.items():
            match=re.search(pattern,normalize(source['excerpt']),re.I)
            if match:
                found[name]=match.group(1).strip()+f' [{sid}]';break
    required=['general','exam'] if broad else []
    if ddc:required+=['ddc_handbook','ddc_academic']
    if cdc:required+=['cdc_handbook','cdc_academic']
    if not all(name in found for name in required):
        return ('I could not find this information in the provided documents.','required_disciplinary_comparison_missing')
    selected=required[:]
    if broad and not re.search(r'\bminimum\b',question,re.I):
        for pair in [('ddc_handbook','ddc_academic'),('cdc_handbook','cdc_academic')]:
            if all(name in found for name in pair):selected.extend(pair)
        selected.extend(name for name in ['rector','extreme','honors'] if name in found)
    if cdc and 'rector' in found:selected.append('rector')
    labels={'general':'General academic-dishonesty wording','exam':'Examination-rule wording','ddc_handbook':'DDC — Student Handbook','ddc_academic':'DDC — Academic Rules','cdc_handbook':'CDC — Student Handbook','cdc_academic':'CDC — Academic Rules','rector':'Approval of suspension or expulsion','extreme':'Extreme acts of dishonesty','honors':'Academic honors and scholarships'}
    parts=[f"**{labels[name]}:**\n> {found[name]}" for name in dict.fromkeys(selected)]
    return ('The retrieved passages use conflicting penalty wording; they do not establish which takes precedence. I cannot present one definitive minimum or maximum as the settled rule.\n\n'+'\n\n'.join(parts)+'\n\nConfirm the applicable interpretation with the Academic Office or the responsible disciplinary authority.','disciplinary_source_conflict')

def room_availability_reply(question,sources):
    """A static policy/contact answer never decides live room inventory."""
    if not (re.search(r'\brooms?\b',question,re.I)
            and re.search(r'availab|vacan',question,re.I)
            and re.search(r'\b(?:today|currently|now|current|latest|at present)\b',question,re.I)):
        return None
    if requested_facets(question) or re.search(r'\b(?:gym|cooler|scholarship|tuition|library|withdraw|FYP|fees?|charges?|mess|parents?|guardians?|visitors?|shopping|bus|transport|gate)\b',question,re.I):return None
    parts=['I cannot confirm live room availability or a personal room assignment from these static documents.']
    supported=False
    for sid,source in sources.items():
        rule=re.search(r'As per policy, single- and double-occupancy rooms.*?The new batch will be accommodated in shared rooms\.',normalize(source['excerpt']),re.I)
        if rule and all(term in rule.group() for term in ('top CGPAs','valid medical reasons','Medical Officer','Hall Management Committee','competent authority')):
            parts.append('The documented eligibility policy is:\n\n> '+rule.group()+f' [{sid}]');supported=True;break
    if re.search(r'contact|email|extension|who|whom',question,re.I):
        mailboxes=[]
        if re.search(r'girls?',question,re.I):mailboxes.append('girlshostel')
        if re.search(r'boys?',question,re.I):mailboxes.append('hostelsupervisor')
        for mailbox in mailboxes or ['warden']:
            for sid,source in sources.items():
                match=re.search(r'([A-Za-z0-9._%+-]*'+mailbox+r'@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\s+Ext:\s*\d+)',normalize(source['excerpt']),re.I)
                if match:
                    parts.append('The requested printed hostel contact is:\n\n> '+match.group(1)+f' [{sid}]');supported=True;break
            else:parts.append('I did not retrieve one of the requested printed contacts; I cannot invent it.')
    return ('\n\n'.join(parts) if supported else 'I could not find this information in the provided documents.'),'static_room_availability_boundary'


def graduation_gpa_reply(question,sources):
    """Compare one supplied CGPA to the actual graduation clause, not awards."""
    if not (re.search(r'\bgraduat(?:e|ion|ing)\b',question,re.I) and re.search(r'\bCGPA(?=\s|[0-4=])',question,re.I)):
        return None
    if len(requested_facets(question))>1 or re.search(r'scholarship|gym|room|library|warning|FYP|duration|medal|award|honou?r|rector|dean|position|all requirements|all conditions|changed|yesterday|announcement|recent|updated',question,re.I):return None
    values={Decimal(v) for v in re.findall(r'\bCGPA\s*(?:(?:is|of|equals|exactly|=)\s*)*([0-4](?:\.\d+)?)(?![\d.])',question,re.I)}
    if len(values)!=1:return None
    supplied=next(iter(values))
    if not Decimal(0)<=supplied<=Decimal(4):return None
    for sid,source in sources.items():
        rule=re.search(FACETS['graduation_cgpa'][2],normalize(source['excerpt']),re.I)
        if not rule:continue
        number=re.search(r'\bof\s+(\d+(?:\.\d+)?)\s+is required for graduation',rule.group(1),re.I)
        if not number:continue
        minimum=Decimal(number.group(1))
        comparison=(f'The supplied CGPA of {supplied} is below {minimum}; completing the courses alone does not satisfy this graduation CGPA requirement.'
                    if supplied<minimum else f'The supplied CGPA of {supplied} is at or above {minimum}. That alone does not verify every other graduation requirement or confer a degree.')
        return 'The indexed graduation rule states:\n\n> '+rule.group(1)+f' [{sid}]\n\n'+comparison+' This is a comparison of supplied information, not verification of a university record.','graduation_gpa_comparison'
    return None


def withdrawal_approval_reply(question, sources):
    """Quote the two actual approval clauses instead of inferring a waiver."""
    if not (re.search(r'withdraw',question,re.I) and re.search(r'HoD|Head of Department|Director|approvals?',question,re.I)):return None
    if requested_facets(question) or re.search(r'FYP|scholarship|sponsorship|loans?|library|gym|hostel|CGPA|recheck',question,re.I):return None
    clauses=None
    for sid,source in sources.items():
        passage=normalize(source['excerpt'])
        general=re.search(r'4\.23\s+(.*?)(?=4\.24)',passage,re.I)
        first=re.search(r'4\.24\s+(.*?)(?=4\.25|$)',passage,re.I)
        if general and first and 'HoD' in general[1] and 'Director' in first[1]:
            clauses=(sid,general[1].strip(),first[1].strip());break
    if clauses is None:return None
    sid,general,first=clauses
    parts=['The retrieved rules state separate withdrawal requirements:',f'> {general} [{sid}]',f'> {first} [{sid}]',
           'These clauses do not state that Director approval replaces or waives the HoD requirement, or that HoD approval waives the first-semester restriction. Confirm the applicable administrative procedure with the Academic Office.']
    if re.search(r'theory|lab',question,re.I):
        for key,source in sources.items():
            rule=re.search(r'4\.8\s+(.*?)(?=4\.9|$)',normalize(source['excerpt']),re.I)
            if rule and re.search(r'passes Theory but fails in Lab',rule[1],re.I):
                parts.extend(['The separate theory/lab rule states:',f'> {rule[1].strip()} [{key}]',
                              'That course-component exception does not state a waiver of the administrative approval clauses.']);break
        else:return None
    return '\n\n'.join(parts),'withdrawal_approval_source_clauses'


def combined_gym_cooler_reply(question,sources):
    if not (re.search(r'\bgym\b',question,re.I) and re.search(r'cooler',question,re.I)):return None
    names='one two three four five six seven eight nine ten eleven twelve'.split()
    number=r'(\d+|'+'|'.join(names)+r')'
    def months(topic):
        patterns=[number+r'\s+(?:months?\s+(?:of\s+)?(?:hostel\s+)?)?'+topic+r'\s*(?:months?|use|charges|subscription)?',
                  topic+r'(?:\s+(?:use|charges|subscription))?\s+(?:for\s+)?'+number+r'\s+months?']
        for pattern in patterns:
            m=re.search(pattern,question,re.I)
            if m:
                value=m[1].lower();return Decimal(value) if value.isdigit() else Decimal(names.index(value)+1)
    gym=months('gym');cooler=months('(?:air[- ]?)?cooler')
    if gym is None or cooler is None:return None
    rates={}
    for sid,source in sources.items():
        text=normalize(source['excerpt'])
        reg=re.search(r'one-time registration fee of Rs\.\s*([\d,]+)',text,re.I)
        monthly=re.search(r'Rs\.\s*([\d,]+)\s+per month',text,re.I)
        if reg and monthly and re.search(r'gym',text,re.I):rates['gym']=(Decimal(monthly[1].replace(',','')),Decimal(reg[1].replace(',','')),sid)
        m=re.search(r'(?:air[- ]?cooler|cooler) charges.*?Rs\.\s*([\d,]+)\s*[/—–-]*\s+per month',text,re.I)
        if m:rates['cooler']=(Decimal(m[1].replace(',','')),sid)
    if len(rates)!=2:return None
    rate,reg,gs=rates['gym'];cr,cs=rates['cooler']
    paid=bool(re.search(r'(?:already|previously) paid[^.;]*registration|registration[^.;]*(?:already|previously) paid',question,re.I))
    if not paid and not re.search(r'first.time|first time|registration|including',question,re.I):return None
    due=Decimal(0) if paid else reg;total=gym*rate+cooler*cr+due
    return (f'Using the printed rates: gym {gym:g} months × PKR {rate:,.0f} = PKR {gym*rate:,.0f} [{gs}]; '
            f'one-time registration due = PKR {due:,.0f} [{gs}]; cooler {cooler:g} months × PKR {cr:,.0f} = PKR {cooler*cr:,.0f} [{cs}]. '
            f'Combined total = **PKR {total:,.0f}**. This is a calculation from the printed snapshot, not a current personal bill.','combined_gym_cooler_source_calculation')


def library_fine_reply(question,sources):
    if not re.search(r'library',question,re.I) or not re.search(r'fine|overdue|late',question,re.I):return None
    if re.search(r'lost|damaged|replacement|different|another|other item|second item|gym|cooler',question,re.I):return None
    names='one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen twenty'.split()
    number=r'(\d+|'+'|'.join(names)+r')'
    counts=re.findall(number+r'\s+(?:undergraduate\s+)?(?:library\s+)?(?:items?|books?)\b',question,re.I)
    days=re.findall(number+r'\s+days?\b',question,re.I)
    if len(counts)!=1 or len(days)!=1:return None
    def value(word):return Decimal(word) if word.isdigit() else Decimal(names.index(word.lower())+1)
    count,late=value(counts[0]),value(days[0])
    for sid,source in sources.items():
        row=re.search(r'Patron Group: Undergraduate;[^\n]*Fine Rate: PKR ([\d,]+)/item/day; Fine Ceiling: PKR ([\d,]+)',source['excerpt'],re.I)
        if not row:continue
        rate,ceiling=(Decimal(x.replace(',','')) for x in row.groups())
        total=count*late*rate
        if total>ceiling:return None
        return (f'Using the printed undergraduate library rate, {count:g} item(s) × {late:g} overdue days × PKR {rate:,.0f}/item/day = **PKR {total:,.0f}** [{sid}]. '
                'This is calculated from the supplied item count and overdue days, not a verified personal library bill.','source_grounded_library_calculation')
    return None


def source_reply(question, sources):
    if re.search(r'warning',question,re.I) and re.search(r'record|eras\w*|deleted|remain|reset|history',question,re.I) and re.search(r'2\.00|reset|record|history',question,re.I):
        for sid,s in sources.items():
            m=re.search(r'5\.7\s+(.*?)(?=Repeating|5\.8|$)',normalize(s['excerpt']),re.I)
            if m:
                text=m.group(1).strip()+f' [{sid}] This establishes a reset of the warning count, not deletion of historical warnings from university records.'
                if re.search(r'scholarship',question,re.I) and re.search(r'every|all|prove|satisfied',question,re.I):
                    text+=' Meeting the warning threshold or resetting its count does not establish that every scholarship condition is satisfied or confirm a personal award.'
                return text,'warning_count_not_record_erasure'
        return 'The retrieved evidence does not establish the warning-count reset rule for this request; please retry or confirm with the Academic Office.','required_warning_reset_rule_missing'
    library=library_fine_reply(question,sources)
    if library:return library
    combined=combined_gym_cooler_reply(question,sources)
    if combined:return combined
    # A directly requested departmental contact is an excerpt lookup. Preserve
    # the printed name as well as its mailbox/extension, avoiding name mutation.
    if (re.search(r'\bSE\b|Software Engineering',question,re.I) and re.search(r'secretary',question,re.I)
        and re.search(r'email|extension|contact',question,re.I)
        and not re.search(r'\bCS\b|Computer Science|Accounts|Financial Assistance|Academic office',question,re.I)):
        for sid,source in sources.items():
            contact=re.search(r'\bSOFTWARE ENGINEERING\s+(Mr\.[\s\S]*?Secretary SE Department[\s\S]*?Ext:\s*\d+)',source['excerpt'],re.I)
            if contact:return 'The printed SE department secretary contact is:\n\n> '+normalize(contact[1])+f' [{sid}]','department_contact_source_excerpt'

    approvals=withdrawal_approval_reply(question,sources)
    if approvals:return approvals
    # A contact-only extract cannot answer a separately requested policy.
    # Keep the full original question on the ordinary generation chain.
    if (any(name.endswith('_contact') for name in requested_facets(question))
        and re.search(r'\b(?:warnings?|probation|attendance|borrow\w*|books?|renew\w*|overdue|fines?|withdraw\w*|recheck\w*|FYP|theory|labs?|scholarships?|sponsorships?|readmission|admission|cooler|mess|parents?|rooms?)\b',question,re.I)):
        return None
    if (re.search(r'\b(?:ai|chatgpt|generative)\b',question,re.I)
        and re.search(r'\bnon[\s-]*lab\b',question,re.I)
        and re.search(r'\b(?:grad(?:e|es|ed|ing)|marks?|marking|course outline)\b',question,re.I)
        and not re.search(r'\blabs?\b',re.sub(r'\bnon[\s-]*labs?\b','',question,flags=re.I),re.I)
        and not ai_reference_intent(question)
        and not requested_facets(question) and not re.search(r'contact|email|scholarship|gym|library|CGPA|\b(?:prompts?|logs?|screenshots?|training|privacy|research|categor\w*|permission|allowed)\b',question,re.I)):
        for sid,source in sources.items():
            rule=re.search(r'A small percentage \(typically 10[-–]15%\).*?These quizzes or demonstrations should take place in the week following the submission deadline\.',normalize(source['excerpt']),re.I)
            if rule:return 'For non-lab assignments, the indexed grading rule states:\n\n> '+rule.group()+f' [{sid}]','ai_nonlab_grading_rule'
        return 'I could not find this information in the provided documents.','required_ai_nonlab_rule_missing'
    if (re.search(r'\b(?:ai|chatgpt|generative)\b',question,re.I)
        and ai_reference_intent(question)
        and not ai_preparation_only(question)
        and re.search(r'\b(?:cit\w*|referenc\w*|attribut\w*)\b',ai_reference_topic(question),re.I)
        and re.search(r'\b(?:images?|figures?|embedded|incorporat\w*|verbatim)\b',question,re.I)
        and not requested_facets(question) and not re.search(r'\b(?:contact|CGPA|grading|marks?|privacy|training|approval|allowed|permission|permitt\w*|scholarship|gym|library|APA|MLA|Chicago|Harvard|style)\b',question,re.I)):
        main=None;continuation=None
        for sid,source in sources.items():
            passage=normalize(source['excerpt'])
            match=re.search(r'8\.\s+Referencing Generative AI Tools\s+(.*)',passage,re.I)
            if match:main=(sid,match.group(1))
            match=re.search(r'\breference list\.\s+Additionally, students must include images of the prompts.*?attribution\.',passage,re.I)
            if match:continuation=(sid,match.group())
        if not main or not continuation:return 'I could not find this information in the provided documents.','required_ai_reference_continuation_missing'
        refs=' '.join(f'[{sid}]' for sid in dict.fromkeys([main[0],continuation[0]]))
        return 'The indexed referencing wording is:\n\n> '+main[1]+' '+continuation[1]+' '+refs,'ai_reference_literal_wording'
    if (re.search(r'\b(?:ai|chatgpt|generative)\b',question,re.I)
        and ai_reference_intent(question) and ai_preparation_only(question)):
        for sid,source in sources.items():
            rule=re.search(r'Using Generative AI/AI tools for research and in the preparation of work does not require citation,.*?Therefore, the use of Generative AI for similar purposes need not be referenced unless an assignment brief specifically states otherwise\.',normalize(source['excerpt']),re.I)
            if rule:return 'For research and preparation, the indexed referencing policy states:\n\n> '+rule.group()+f' [{sid}]','ai_preparation_reference_rule'
        return 'I could not find this information in the provided documents.','required_ai_reference_rule_missing'
    availability=room_availability_reply(question,sources)
    if availability:return availability
    graduation=graduation_gpa_reply(question,sources)
    if graduation:return graduation
    if (re.search(r'scholarship|financial aid|academic honou?r',question,re.I)
        and re.search(r'cheat|dishonest|unfair means|disciplinary|\bDDC\b|\bCDC\b',question,re.I)):
        honors=None;conduct=None
        for sid,source in sources.items():
            passage=normalize(source['excerpt'])
            match=re.search(r'8\.18\s+(.*?)(?=8\.19\b|$)',passage,re.I)
            if match:honors=match.group(1).strip()+f' [{sid}]'
            match=re.search(r'(Failure to meet these standards.*?scholarship, etc\.)',passage,re.I)
            if match:conduct=match.group(1).strip()+f' [{sid}]'
        if honors:
            text='The Academic Rules state:\n\n> '+honors
            if conduct:text+='\n\nThe Student Handbook describes possible disciplinary recommendations:\n\n> '+conduct
            if re.search(r'financial aid',question,re.I) or conduct:
                text+='\n\nThe scholarship rule does not establish automatic cancellation of every form of financial aid.'
                if conduct:text+=' The handbook describes recommendations that may be made; confirm the applicable decision with the responsible university office.'
            return text,'disciplinary_honors_conditions'
    discipline=disciplinary_reply(question,sources)
    if discipline:return discipline
    if requested_facets(question)==['financial_contact'] and re.search(r'\bwho\s+(?:manages|handles|coordinates)\b',question,re.I) and not re.search(r'eligib|conditions?|duration|semesters?|\b(?:and|also)\b',question,re.I):
        for sid,source in sources.items():
            match=re.search(FACETS['financial_contact'][2],normalize(source['excerpt']),re.I)
            if match:return ('The printed Financial Assistance office contact is:\n\n> '+match[1]+f' [{sid}]','financial_assistance_manager_contact')
        return ('I could not find the requested contact in the retrieved passages.','required_financial_manager_missing')
    if generic_assistance_contact(question):
        for sid,source in sources.items():
            match=re.search(FACETS['financial_contact'][2],normalize(source['excerpt']),re.I)
            if match:
                return ('If you mean financial assistance, the printed contact is:\n\n> '+match.group(1)+f' [{sid}]\n\nIf you mean another kind of assistance, please specify the service.','qualified_assistance_contact')
        return ('I could not find this information in the provided documents.','required_assistance_contact_missing')
    fyp=fyp_deficiency_reply(question,sources)
    if fyp:return fyp
    warning=second_warning_reply(question,sources)
    if warning:return warning
    summer=summer_enrollment_reply(question,sources)
    if summer:return summer
    wording=policy_wording_reply(question,sources)
    if wording:return wording
    room=hostel_room_reply(question,sources)
    if room:return room
    funding=merit_gpa_reply(question,sources)
    if funding:return funding
    continuation=merit_continuation_reply(question,sources)
    if continuation:return continuation
    """Quote an applicable retrieved rule; never supply missing policy from code."""
    if exhaustive_admissions(question):
        parts=[];has_readmission=False;has_closure=False
        for sid,s in sources.items():
            t=normalize(s['excerpt'])
            readmission=bool(re.search(r'3\.1\s|Readmission of',t,re.I))
            closure='3.27' in t
            if readmission or closure:
                parts.append('> '+t+f' [{sid}]')
                has_readmission|=readmission;has_closure|=closure
        if has_readmission and has_closure:
            return 'The following retrieved passages establish the selected covered rules:\n\n'+'\n\n'.join(parts),'selected_admission_source_rules'
        return None
    if re.search(r'\bgym\b',question,re.I) and not re.search(r'cooler|mess|hostel fee',question,re.I):
        count=re.search(r'\b(\d+|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)[ -]+(?:months?|monthly)\b',question,re.I)
        if count and re.search(r'first|registration|including',question,re.I):
            names='one two three four five six seven eight nine ten eleven twelve'.split()
            value=count.group(1).lower();months=Decimal(value) if value.isdigit() else Decimal(names.index(value)+1)
            for sid,s in sources.items():
                t=normalize(s['excerpt'])
                semester=re.search(r'Rs\.\s*([\d,]+)\s+per semester',t,re.I)
                monthly=re.search(r'Rs\.\s*([\d,]+)\s+per month',t,re.I)
                registration=re.search(r'one-time registration fee of Rs\.\s*([\d,]+)',t,re.I)
                if not all((semester,monthly,registration)):continue
                sem,rate,reg=(Decimal(m.group(1).replace(',','')) for m in (semester,monthly,registration))
                unpaid=bool(re.search(r"(?:not|never|haven't|have not|has not).{0,24}(?:paid|registered)|registration.{0,24}(?:unpaid|not paid)",question,re.I))
                already_paid=not unpaid and bool(re.search(
                    r'(?:already|previously) paid (?:the |my |gym |one-time )*registration|'
                    r'(?:already|previously) registered|registration.{0,30}(?:already|previously) paid|'
                    r'no (?:new |additional )?registration|not (?:joining.{0,20})?(?:for )?the first time',question,re.I))
                due=Decimal(0) if already_paid else reg
                total=months*rate+due
                registration_note='registration already paid, not charged again' if already_paid else 'first-time registration'
                reply=f'Using the printed gym rates, {months:g} monthly payments ({registration_note}) total {months:g} × PKR {rate:,.0f} + PKR {due:,.0f} = **PKR {total:,.0f}** [{sid}].'
                if re.search(r'compar|against|versus|with semester|semester option',question,re.I):
                    reply+=f' The semester option with the same registration treatment is PKR {sem:,.0f} + PKR {due:,.0f} = **PKR {sem+due:,.0f}**; the absolute difference is **PKR {abs(total-sem-due):,.0f}** [{sid}].'
                return reply+' These are calculations from the printed snapshot, not a current personal bill.','source_grounded_gym_calculation'
    if re.search(r'quot|excerpt|source passage',question,re.I) and re.search(r'contact|email|extension',question,re.I):
        contacts=[(r'financial.assistance',r'FINANCIAL ASSISTANCE'),(r'accounts',r'ACCOUNTS OFFICE'),(r'library',r'LIBRARY')]
        selected=[heading for intent,heading in contacts if re.search(intent,question,re.I)]
        if len(selected)==1:
            for sid,s in sources.items():
                m=re.search(r'\b'+selected[0]+r'\b[\s\S]{0,2000}?\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\s*\nExt:\s*\d+(?:/\d+)?',s['excerpt'],re.I)
                if m:
                    quote='\n'.join('> '+line for line in m.group().strip().splitlines())
                    return 'The printed supporting contact excerpt is:\n\n'+quote+f' [{sid}]','contact_source_excerpt'
    cases=theory_cases(question)
    if cases:
        parts=[]
        for case in cases:
            found=None
            for sid,s in sources.items():
                match=re.search(re.escape(case)+r'\s+(.*?)(?=4\.\d+\b|$)',normalize(s['excerpt']),re.I)
                if match:
                    found=f'{match.group(1).strip()} [{sid}]';break
            if found is None:return None
            parts.append(found)
        return '\n\n'.join(parts), 'theory_lab_source_rule'
    if explicit_multipart(question):
        parts=[]
        for name in requested_facets(question):
            for sid,s in sources.items():
                m=re.search(FACETS[name][2],normalize(s['excerpt']),re.I)
                if m:
                    parts.append(m.group(1).strip()+f' [{sid}]');break
            else:return None
        return '\n\n'.join(parts),'explicit_multipart_source_rules'
    personal_change=re.search(r'\bmy\s+(?:cumulative\s+)?CGPA\s+(?:has\s+)?(?:changed|increased|improved|updated)',question,re.I)
    if (not personal_change and re.search(r'graduat',question,re.I) and re.search(r'CGPA',question,re.I)
        and re.search(r'changed|yesterday|announcement|updated',question,re.I)):
        for sid,s in sources.items():
            m=re.search(FACETS['graduation_cgpa'][2],normalize(s['excerpt']),re.I)
            if m:return ('I cannot verify the alleged recent change from these static documents. The indexed rules state:\n\n'+m.group(1)+f' [{sid}]\n\nConfirm any newer official announcement with the Academic Office.','unverified_policy_update')
    if re.search(r'rector.{0,8}list',question,re.I):
        parts=[]
        for pattern in [r'7\.3\s+(.*?)(?=7\.4|$)',r'7\.5\s+(.*?)(?=Dean|7\.6|$)']:
            for sid,s in sources.items():
                m=re.search(pattern,normalize(s['excerpt']),re.I)
                if m:
                    clause=m.group(1).strip()
                    if pattern.startswith(r'7\.3'):
                        threshold=re.search(r'Students earning.*?30 credit hours',clause,re.I)
                        if threshold:clause=threshold.group()+'.'
                    parts.append(clause+f' [{sid}]');break
        if parts:
            return (' '.join(parts)+' The supplied wording does not clearly specify the period to which the 30 credit hours apply. Confirm that interpretation with the Academic Office; a cumulative requirement cannot be established from these passages.', 'rector_ambiguity')
    if re.search(r'\blab',question,re.I) and re.search(r'\b(?:AI|generative|2\.5)',question,re.I) and re.search(r'how long|duration|half.hour|2\.5|schedule|timing|time period',question,re.I):
        for sid,s in sources.items():
            t=normalize(s['excerpt'])
            m=re.search(r'When the use of generative AI is permitted,.*?(?=4\)|$)',t,re.I)
            if m and 'first 2.5' in m.group():
                text=(m.group().strip()+f' [{sid}] The wording is ambiguous: it describes a 2.5-hour session, a final half-hour quiz, and prompts from the first 2.5 hours. It does not unambiguously establish a consistent total duration or AI-use period. Confirm the schedule with the lab instructor.')
                if re.search(r'permitt|permission|allowed|when',question,re.I):
                    permission=re.search(r'In general, the use of generative AI.*?2\)\s*10% of the labs will allow the use of generative AI tools\.',normalize(s['excerpt']),re.I)
                    if not permission:return None
                    text='The documented lab permission rules state:\n\n> '+permission[0]+f' [{sid}]\n\n'+text
                if re.search(r'yesterday|changed|announcement|recent|updated',question,re.I):
                    text+=' These static PDFs cannot verify an alleged change yesterday or establish that no later change occurred. Confirm newer official announcements with the Academic Office.'
                return text,'ai_lab_ambiguity'
    return None

def align_policy_claims(question, text, sources):
    """Protect the observed scholarship/medal substitution, including model prose."""
    if not re.search(r'merit[- ]scholarship',question,re.I):return text
    if not re.search(r'\bloans?\b',question,re.I) and re.search(r'\b(?:study loans?|financial assistance\s*\(loan\))\b|financial assistance\s*\(loan\)',text,re.I):
        raise ValueError('The response could not be validated: merit scholarship response introduced an unrequested loan scheme.')
    patterns=[r'(?:failed|repeated|withdrawn).*?course',r'(?:less|more).*?credit hours',r'standard courses']
    lines=[]
    for line in text.splitlines():
        if re.search(r'position medal',line,re.I):lines.append(line);continue
        # A composite sentence can cite the exact-load paragraph for its other
        # conditions while omitting the separate semester-GPA clause. Add the
        # latter's own locator only for an identical retrieved numeric rule;
        # never rewrite a different threshold or borrow the loan CGPA rule.
        line_ids={sid.upper() for group in re.findall(r'\[([Ss]\d+(?:\s*[,;]\s*[Ss]\d+)*)\]',line)
                  for sid in re.findall(r'[Ss]\d+',group)}
        def semester_locator(match):
            prefix=re.split(r'[;.!?]',line[:match.start()])[-1]
            suffix=line[match.end():]
            if (re.search(r'\bnot\b|rather than|instead of|doesn.t require',prefix[-70:],re.I)
                or re.match(r'\s+(?:is |are )?not (?:required|the requirement|the threshold)',suffix,re.I)):
                return match[0]
            number=Decimal(match[1])
            supporting=[]
            for sid,source in sources.items():
                rule=re.search(r'Continuation of merit scholar\s*ship (?:is subject to maintaining|requires) semester GPA of ([\d.]+) or higher\.',normalize(source['excerpt']),re.I)
                if rule and Decimal(rule[1])==number:supporting.append(sid)
            if any(sid in line_ids for sid in supporting):return match[0]
            if not supporting:
                raise ValueError('The response could not be validated: the cited evidence does not establish the merit-scholarship semester-GPA threshold.')
            return match[0]+f' [{supporting[0]}]'
        line=re.sub(r'\bsemester[- ]GPA (?:of )?([0-4](?:\.\d+)?) or higher\b',semester_locator,line,flags=re.I)
        claims=[p for p in patterns if re.search(p,line,re.I)]
        if claims:
            ids=re.findall(r'\[(S\d+)\]',line)
            for sid in ids:
                if sid not in sources:continue
                if 'medal' in categories(sources[sid]) and 'scholarship' not in categories(sources[sid]):
                    matches=[k for k,s in sources.items() if 'scholarship' in categories(s)
                             and all(re.search(p,normalize(s['excerpt']),re.I) for p in claims)]
                    if not matches:
                        raise ValueError('The response could not be validated: scholarship conditions cite medal evidence without supporting scholarship evidence.')
                    line=line.replace(f'[{sid}]',f'[{matches[0]}]')
        lines.append(line)
    return '\n'.join(lines)

def preserve_policy_language(text, sources):
    # Only align identified wording to the cited rule, not arbitrary sentences.
    lines=[]
    for line in text.splitlines():
        evidence=' '.join(normalize(sources[k]['excerpt']) for k in re.findall(r'\[(S\d+)\]',line) if k in sources)
        if re.search(r'withdraw',line,re.I) and re.search(r'HoD[^\n]*\b(?:or|rather than|instead of|in place of|replac\w*|substitut\w*)\b[^\n]*Director|Director[^\n]*\b(?:or|rather than|instead of|in place of|replac\w*|substitut\w*)\b[^\n]*HoD',line,re.I):
            # The two withdrawal clauses establish separate requirements; no
            # retrieved clause authorizes substituting one approving office.
            supporting=[]
            for sid,source in sources.items():
                passage=normalize(source['excerpt'])
                hod=re.search(r'Request for withdrawal must be approved by the HoD\.',passage,re.I)
                first=re.search(r'Students are not allowed to withdraw from any course in the first semester unless necessitated by unavoidable circumstances\. Such a r\s*equest must be approved by the Director of the campus\.',passage,re.I)
                if hod and first:supporting.append((sid,hod[0],first[0]))
            if not supporting:
                raise ValueError('The response could not be validated: alternative withdrawal approval is not established by the retrieved clauses.')
            sid,hod,first=supporting[0]
            line='**Documented withdrawal approval clauses:** '+hod+f' [{sid}] '+first+f' [{sid}]'
        if re.search(r'this should be referenced within the text or content of the assignment',evidence,re.I):
            line=re.sub(r'\bmust be referenced\b','should be referenced',line,flags=re.I)
        if re.search(r'This grading distribution should be clearly stated in the course outline\.',evidence,re.I):
            line=re.sub(r'\b(grading distribution(?:\s*\([^)]*\))?)\s+(?:must|has to|is required to)\s+be\s+(?:clearly\s+)?stated\b',r'\1 should be clearly stated',line,flags=re.I)
            line=re.sub(r'\b(course outline) (?:must|has to|is required to) (?:clearly )?state (?:the )?grading distribution\b',r'\1 should clearly state the grading distribution',line,flags=re.I)
        if re.search(r'These quizzes or demonstrations should take place in the week following the submission deadline\.',evidence,re.I):
            line=re.sub(r'\b((?:These )?quizzes or demonstrations) must take place\b',r'\1 should take place',line,flags=re.I)
        if (re.search(r'second|2nd|2\s*nd',line,re.I) and re.search(r'warning',line,re.I)
            and re.search(r'new course',line,re.I) and re.search(r'register|approval|approved|recommend',line,re.I)
            and not re.search(r'does not (?:contain|establish)|cannot establish',line,re.I)
            and not re.search(WARNING_APPROVAL,evidence,re.I)):
            raise ValueError('The response could not be validated: the cited passage does not contain the second-warning approval rule.')
        if re.search(r'application should r\s*each the Examination O\s*ffice',evidence,re.I):
            line=re.sub(r'\b(applications?\b[^.!?\n]{0,100}?)\bmust reach\b',r'\1should reach',line,flags=re.I)
        if (re.search(r'recheck',line,re.I) and re.search(r'fee|refund',line,re.I)
            and re.search(r'only if|not (?:be )?refunded|no refund',line,re.I)
            and not re.search(r'(?:does not|cannot|doesn.t).{0,35}(?:state|establish|confirm|say)|not.{0,15}only if',line,re.I)
            and re.search(r'Rechecking fee will be refunded if there is an in\s*crease in marks',evidence,re.I)
            and not re.search(r'(?:Rechecking fee|All fees).{0,80}(?:non[- ]*refundable|not (?:be )?refunded|only if)',evidence,re.I)):
            raise ValueError('The response could not be validated: rechecking refund claim added an unsupported exclusive condition.')
        if (re.search(r'should apply on the prescribed Financial Aid form',evidence,re.I)
            and re.search(r'Financial Aid form',line,re.I)
            and not re.search(r'not.{0,20}must apply|does not.{0,30}must apply',line,re.I)):
            line=re.sub(r'\bmust apply\b|\b(?:are|is) required to apply\b','should apply',line,flags=re.I)

        if re.search(r'Should not register for more than five courses',evidence,re.I):
            line=re.sub(r'\bmust not register for more than five courses\b','should not register for more than five courses',line,flags=re.I)
        if re.search(r'A minimum of TEN\s*\(10\) students should register in a summer course',evidence,re.I):
            line=re.sub(r'(\bminimum of (?:ten\s*(?:\(10\))?|10) students)\s+(?:must|are required to)\s+register\b',r'\1 should register',line,flags=re.I)
        if re.search(r'CGPA falls below the minimum|CGPA.*below 2\.00',evidence,re.I):
            line=re.sub(r'(?:keeping|keeps?|maintain(?:ing)?) (?:your |their |the student.s )?CGPA above', 'maintaining CGPA at or above',line,flags=re.I)
        if re.search(r'Retake examination application may be considered',evidence,re.I):
            line=re.sub(r'\b(?:A student|You) can get a retake for', 'A retake application may be considered for',line,flags=re.I)
        lines.append(line)
    return '\n'.join(lines)

def align_rechecking_citations(question, text, sources):
    """A prescribed rechecking form/fee cannot cite an unrelated retake table."""
    if not re.search(r'recheck', question, re.I):return text
    lines=[]
    for line in text.splitlines():
        if re.search(r'prescribed (?:form|fee)',line,re.I):
            ids=re.findall(r'\[(S\d+)\]',line)
            # Exact documented proposition, not general word overlap.
            support=[k for k,s in sources.items() if re.search(r'prescribed form together with rechecking fee',normalize(s['excerpt']),re.I)]
            for sid in ids:
                if sid in sources and 'retake' in categories(sources[sid]) and 'rechecking' not in categories(sources[sid]):
                    if not support:
                        raise ValueError('The response could not be validated: a rechecking form/fee claim cites retake evidence without supporting rechecking evidence.')
                    line=line.replace(f'[{sid}]', '' if any(k in ids for k in support) else f'[{support[0]}]')
        lines.append(line)
    return '\n'.join(lines)
