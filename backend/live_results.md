# Live Functional Test Results

**TC_F_01 Basic skill check**
*Query*: Does the student know React?
*Condition*: verify_tech
*Response*: Verdict: Inconclusive. The resume lists 'React' as a skill, but the lack of GitHub repositories using 'React' raises doubts. Recommendation: Ask follow-up questions to assess hands-on experience with React.
---
**TC_F_02 Multiple skills query**
*Query*: Does the student know React and Node?
*Condition*: verify_tech
*Response*: Verdict: The evidence does not support the claim. The candidate's resume and GitHub profile lack any mention or demonstration of 'React and Node' expertise. Recommendation: Investigate further or request code examples to validate the candidate's proficiency.
---
**TC_F_03 Unknown skill**
*Query*: Does the student know Rust?
*Condition*: verify_tech
*Response*: Verdict: The evidence does NOT support the claim. The candidate's resume and GitHub profile do not mention Rust, contradicting their statement. Recommendation: Investigate further to verify the candidate's proficiency in Rust.
---
**TC_F_04 Conceptual question**
*Query*: What is blockchain?
*Condition*: general_qa
*Response*: To answer your question, blockchain is a decentralized, distributed ledger technology that records transactions across a network of computers. It's a secure, transparent, and tamper-proof way to store data. Although not listed in your skills, I noticed you mentioned CypherQL, which is related to graph databases and has some connections to blockchain concepts. Can you tell me how you think blockchain technology could be applied in a real-world scenario, given your experience with projects like GenAI Interactive Learning Games?
---
**TC_F_05 Mixed query**
*Query*: Does student know React and what is React?
*Condition*: verify_tech
*Response*: Verdict: Inconclusive. The resume lists 'React' as a skill, but the lack of GitHub repositories using 'React' raises doubts. Recommendation: Ask follow-up questions to assess hands-on experience with React.
---
**TC_F_06 Project-based query**
*Query*: Show projects using Angular
*Condition*: verify_project
*Response*: Verdict: The evidence does not support the claim. The resume and GitHub profile do not mention a project called "Angular". It's possible the candidate is referring to the existing framework "Angular", not a personal project. Recommendation: Investigate further to clarify the claim.
---
**TC_F_07 Resume-only skill**
*Query*: Does student know Docker?
*Condition*: verify_tech
*Response*: Verdict: The evidence does not support the claim. The candidate's resume and GitHub profile lack any mention of Docker, contradicting their statement. Recommendation: Investigate further with specific Docker-related questions to assess their actual knowledge.
---
**TC_F_08 Case-insensitive input**
*Query*: rEACT knowledge?
*Condition*: verify_tech
*Response*: Verdict: Inconclusive. 
The resume lists 'REACT' as a skill, but the lack of GitHub repositories using 'REACT' raises doubts. Recommendation: Ask behavioral questions to assess practical experience with 'REACT'.
---
**TC_F_09 Synonym handling**
*Query*: Does student know frontend frameworks?
*Condition*: verify_tech
*Response*: Verdict: No, the evidence does not support the claim. The candidate's resume and GitHub profile lack any mention of 'frontend frameworks', contradicting their statement. Recommendation: Investigate further with specific framework-related questions to assess their actual knowledge.
---
**TC_F_10 Follow-up question**
*Query*: What about backend?
*Condition*: verify_tech
*Response*: Verdict: No, the evidence does not support the claim. The candidate's resume and GitHub profile lack any mention of backend skills, contradicting their statement. Recommendation: Investigate further to verify the candidate's backend experience.
---
