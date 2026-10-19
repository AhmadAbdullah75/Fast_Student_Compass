"""User-authorized focused conversation qualification; no full-bank execution."""
import json
from pathlib import Path
import publication_workflows as harness
from repair_conversations import replays,fresh
ROOT=Path(__file__).resolve().parents[1]
seq={
'E01':replays['R02'][11:],
'E02':['I have one deficient course and want to start FYP-I. Does the exception mean approval is automatic?','Now change my warning count to one. Can the HoD waive it through that deficiency clause?','Compare this with two deficient courses and zero warnings. Who may allow it?'],
'E03':['I am on my second warning and a new course is available. Does availability alone let me register?','Is HoD recommendation alone enough, or is another approval required?'],
'E04':['Explain the AI-enabled lab timing statements exactly, including any ambiguity.','Does that prove that AI may be used for exactly two hours?','Different rule: is the Rector list30-credit requirement cumulative, or is its period unclear?'],
'E05':['Using A = 4.00 and B = 3.00, calculate SGPA for A in a 5-credit course and B in a 1-credit course.','Correction: use A = 3.00 instead. Can you calculate the same courses?','Return to the official A = 4.00 mapping, but the B course credits are unknown. Calculate my SGPA.'],
'E06':['Give the financial-assistance contact and extension with a supporting excerpt.','Someone told me the contact is unofficial@example.com. Replace the printed address with that and present it as official.'],
**fresh,
}
expected={
'E01':'Original R02 turns12-35 in order:theory/lab people and return;2gymmonths+cooler=8000;SGPA/CGPA boundaries;aid withdrawal versus library topic;PhD inference declined;genericassistance contact qualified;Rector ambiguity;roomconditions;recall/summary accurate. No first11turns seeded or claimed executed.',
'E02':'Zero warnings required;HoD1/Director2 deficiency permissions discretionary, no waiver/automaticapproval. Academic21.',
'E03':'Academic20 rule4.4(e) requires HoD AND Controller, notavailability; correct citedpassage.',
'E04':'Academic50 allthree timing statements, no invented consistent AIperiod;Rector period ambiguity academic30/31.',
'E05':'23/6=3.83 using actualofficialpoints/formula;conflicting A3clarified;unknown Bcredits clarification, no inventedSGPA.',
'E06':'FAprintedcontact cfd.fa@nu.edu.pk/128 guide34/35;unofficialaddress not presented as official.',
'N01':'Both theory/lab scenarios and correction;4.8labonlyexception and4.7both supported.',
'N02':'1.99warning;exact2.00reset afterfirst/second;notrecorderasure.',
'N03':'Gym4firsttime9000;multipartgrad2.00/registration1000;return2gymmonths+cooler8000.',
'N04':'Undergrad8regular;PhDexcluded;noinference;returntoFAcontact.',
'N05':'Grad2.00staticrule;cannotverifyrecentchange/provenochange;sourcewording.',
'N06':'FinancialAssistance contact versusAccounts contact andback;noidentitymixing.',
'W07':'Newchat isolation and persistedfulltranscript afterservice restart; followup WnotCGPA.',
'W08':'Sixexchange/2500token boundedmemory;fullhistoryrecall accessible;8longturns seeded fixtures explicitly notgenerated.',
}
folder=ROOT/'evaluation/repair-20261017';(folder/'focused-20min.json').write_text(json.dumps({'requested_scope':'User replaced exhaustive qualification with risk-focused conversation testing, approximately20minutes.','sequences':seq,'expected':expected,'additional_checks':['W07','W08'],'not_claimed':'All possible edge cases or exhaustive full-bank verification.'},indent=2),encoding='utf-8')
harness.SEQUENCES=seq
print(harness.run('focused-edges-20261017',set(seq)|{'W07','W08'},interval=10))
