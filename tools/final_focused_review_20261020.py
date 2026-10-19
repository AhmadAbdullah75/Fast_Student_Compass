"""Record explicit source comparison; provenance checks are not semantic grading."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
folder = ROOT/'reports/publication/final-focused-20261020'
report = json.loads((folder/'workflows.json').read_text(encoding='utf-8'))
notes = {
 'C1': [
  'Academic p20 rules 4.7/4.8 support both repeats for Ali and lab-only/withdrawal exception for Sara.',
  'Academic p20 rules 4.6/4.8/4.9 support corrected improvement case and separate Sara exception. Intro says not both can withdraw; individual explanations are correct.',
  'Lists the two preceding user questions exactly, excludes itself, no policy citations needed; malformed word order routed to saved history.',
 ],
 'C2': [
  'Guidebook p24 gives 2000/month and 1000 registration; 4*2000+1000=9000.',
  'Guidebook pp23/24 support 3000 cooler/month and gym rates; 6000+1000+6000=13000, one consistent total.',
  'Handbook p33 undergraduate row gives 10/item/day; 2*9*10=180.',
  'Explicit replacement correction gives 1*12*10=120, no stale second item or gym amount.',
 ],
 'C3': [
  'Handbook p20 states semester GPA >=3 and internal-scholarship CGPA suspension; Academic p24 supplies below-2 warning threshold. Both GPAs distinguished; no personal award guarantee.',
  'Academic p25 rule5.7 supports >=2 reset after first/second warning; neither historical deletion nor satisfaction of all scholarship conditions inferred.',
  'Declines deriving excluded PhD sponsorship from undergraduate coverage, without claiming original PDFs lack postgraduate material.',
  'Guidebook pp34/35 financial assistance block supports Nooria Fatima, cfd.fa@nu.edu.pk, extension128; no unrelated IT/hostel contact copied.',
 ],
 'C4': [
  'Unqualified deadline asks clarification and invents no policy.',
  'Academic pp26/27 support prescribed form+fee, should reach within seven days, refund if marks increase; no unsupported only-if inference.',
  'Handbook p24 and Academic pp35/36 support conflicting DDC/CDC wording; retains Rector approval and declines choosing precedence/guaranteeing penalty.',
  'Academic p50 supports instructor permission, 10percent, all three timing statements. Ambiguity and static-document recency limit explicitly retained.',
 ],
}
rows=[]
for sequence in report['results']:
    assert sequence['execution_status']=='COMPLETED'
    assert len(sequence['turns'])==len(notes[sequence['id']])
    for i, turn in enumerate(sequence['turns']):
        assert turn['status']=='completed'
        citations=turn['citations']
        retrieved={d['chunk_id']:d for d in turn.get('diagnostics',{}).get('retrieved',[])}
        for citation in citations:
            assert citation['chunk_id'] in retrieved
            assert citation['references']==retrieved[citation['chunk_id']]['references']
        assert set(re.findall(r'\[(S\d+)\]',turn['answer'])) <= {c['id'] for c in citations}
        rows.append({'id':f"{sequence['id']}.{i+1}",'question':turn['question'],
                     'answer_review':'PASS','citation_provenance':'PASS',
                     'supporting_evidence_review':notes[sequence['id']][i],
                     'source_pages':sorted({f"{r['id']}:{r['pdf_page']}" for c in citations for r in c['references']}),
                     'retrieval_review':'supporting evidence present' if citations else 'no policy retrieval required for local recall, clarification or scope refusal'})
(folder/'semantic-review.json').write_text(json.dumps({'pipeline_revision':report['pipeline_revision'],
 'reviewer':'Codex explicit answer-to-retrieved-passage comparison; not independent university review',
 'reviewed_turns':len(rows),'material_failures':0,'results':rows},indent=2),encoding='utf-8')
print(json.dumps({'reviewed':len(rows),'material_failures':0,'revision':report['pipeline_revision']}))
