"""Deterministic conversation intents, with no model or storage side effects."""
import re


def normalized_request(question):
    text=' '.join(re.sub(r'[^a-z0-9 ]',' ',question.lower()).split())
    text=re.sub(r'\bi ve\b','i have',text)
    return re.sub(r'^(?:please\s+)?(?:(?:can|could|would|will)\s+you\s+(?:please\s+)?)?(?:(?:tell|remind)\s+me\s+|show\s+me\s+)?','',text).strip()


def is_history_request(question):
    text=normalized_request(question)
    patterns=[
        r'(?:what|which) (?:(?:questions|things) )?(?:have i|i have|did i|i) ask(?:ed)?(?: you)?(?: (?:before|earlier|previously|so far))?(?: in (?:this|our) (?:chat|conversation))?',
        r'(?:(?:list|show|repeat) )?(?:all )?my (?:previous |earlier )?questions(?: (?:so far|in (?:this|our) (?:chat|conversation)))?',
        r'(?:(?:list|show|repeat|enumerate) )?(?:all )?(?:the )?questions (?:that )?(?:i(?: have)?|have i|did i) ask(?:ed)?(?: you)?(?: (?:before|earlier|previously|so far))?(?: in (?:this|our|the) (?:chat|conversation))?',
    ]
    return any(re.fullmatch(pattern,text) for pattern in patterns)


def saved_recap(turns):
    substantive=[]
    for turn in turns:
        if turn.get('status')!='completed' or is_history_request(turn['question']):continue
        if turn.get('diagnostics',{}).get('route') in ('capabilities','conversation_history','conversation_summary'):continue
        if re.search(r'\b(?:summary|summarize|summarise|recap)\b',turn['question'],re.I) and re.search(r'\b(?:chat|conversation|discussion)\b',turn['question'],re.I):continue
        substantive.append(turn)
    if not substantive:return 'There are no earlier substantive questions to summarize in this saved chat.'
    # Sample across the discussion, rather than repeating every question.
    chosen=substantive if len(substantive)<=4 else [substantive[round(i*(len(substantive)-1)/3)] for i in range(4)]
    def excerpt(text,limit):
        text=re.sub(r'\[S\d+(?:\s*,\s*S\d+)*\]','',text or '')
        text=' '.join(re.sub(r'[*#>`]','',text).split())
        return text if len(text)<=limit else text[:limit].rsplit(' ',1)[0]+'…'
    rows=[]
    for turn in chosen:
        citations=turn.get('citations',[])
        incomplete=bool(citations) and any(not c.get('excerpt') or not c.get('references') for c in citations)
        reply=('Source records for this saved reply are incomplete; review the original exchange.'
               if incomplete else excerpt(turn.get('answer'),260))
        rows.append(f"- You asked: {excerpt(turn['question'],110)}\n  Saved reply excerpt: {reply}")
    return (f'Brief recap of this saved conversation ({len(chosen)} of {len(substantive)} substantive exchanges):\n\n'+'\n\n'.join(rows)+
            '\n\nThis is an extractive recap of saved replies, not a new verification of policy. The original answers and their sources remain above.')


DEADLINE_TOPICS={
    'withdrawal':(r'withdraw', 'What is the documented deadline for withdrawing from a course?'),
    'rechecking':(r'recheck', 'What is the documented application deadline for examination rechecking?'),
    'library':(r'library|borrow|renew|books?', 'What is the documented return or renewal period for undergraduate library items?'),
    'financial assistance':(r'scholarship|financial assistance|financial aid', None),
    'admission':(r'admission',None),
}


def deadline_reference(question, turns):
    """Resolve only a uniquely established question topic; never invent a date."""
    text=normalized_request(question)
    if not re.fullmatch(r'(?:(?:what(?: s| is)?|when(?: s| is)) (?:the |my |its |that )?(?:deadline|last date)|(?:the )?deadline|when is (?:it|that) due|by when)',text):return None
    recent=[t for t in turns if t.get('status')=='completed' and
            t.get('diagnostics',{}).get('route') not in ('capabilities','conversation_history','conversation_summary','clarification')][-6:]
    topics={name for name,(pattern,_) in DEADLINE_TOPICS.items() if any(re.search(pattern,t['question'],re.I) for t in recent)}
    if len(topics)==1:
        topic=next(iter(topics));resolved=DEADLINE_TOPICS[topic][1]
        if resolved:return {'question':resolved,'unresolved':False,'topic':topic}
    return {'question':question,'unresolved':True,'topics':sorted(topics)}
