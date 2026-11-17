# PAP-0.5 methodology summary

PAP means Procurement Authorization Policy. This newly written descriptive summary is neither the normative policy text nor an executable evaluator.

An action proposal, independent authorization decision, committed effect and verified task completion are separate events. Delegation/scope, approved vendor and centre, amount, duplicate/state conditions, approval validity and exposure accounting constrain procurement. Agent-written approval is unavailable; trusted approvals have separate authority and timing.

R5 VENDOR_BLOCKED and CC_NOT_DELEGATED are the two controlled eligible denial reasons. A denied submission creates no PR, no token and no state effect. A permitted submission is workflow progress, not purchase completion. A purchase requires a matching submitted PR, authorization and correct final effects/ledger.

B0 independently simulates business execution with observational PAP shadow. B1 enforces and terminates on denial. B2 allows recovery only under its frozen predicate and bound. The calculation scripts do not evaluate policy; the separate mechanism/pap/evaluator.py derivative does. The whole normative archive remains excluded; selected original implementation is now in mechanism/pap under the proposed private MIT scope. P5-12 remains OPEN / NOT_SPECIFIED.
