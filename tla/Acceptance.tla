--------------------------- MODULE Acceptance ---------------------------
EXTENDS Naturals, FiniteSets, Sequences

CONSTANTS Requests, Limit
VARIABLES closed, watermark, revoked, accepted, spent, history
vars == <<closed, watermark, revoked, accepted, spent, history>>

Init == /\ closed = FALSE /\ watermark = FALSE /\ revoked = FALSE
        /\ accepted = {} /\ spent = 0 /\ history = <<>>

Close == /\ ~closed /\ closed' = TRUE
         /\ UNCHANGED <<watermark, revoked, accepted, spent, history>>

Watermark == /\ ~watermark /\ watermark' = TRUE
             /\ UNCHANGED <<closed, revoked, accepted, spent, history>>

Revoke == /\ ~revoked /\ revoked' = TRUE
          /\ UNCHANGED <<closed, watermark, accepted, spent, history>>

Accept(r) == /\ r \in Requests \ accepted
             /\ closed /\ watermark /\ ~revoked /\ spent < Limit
             /\ accepted' = accepted \cup {r}
             /\ spent' = spent + 1
             /\ history' = Append(history,
                  [id |-> r, closed |-> closed, watermark |-> watermark,
                   authorised |-> ~revoked])
             /\ UNCHANGED <<closed, watermark, revoked>>

Retry(r) == /\ r \in accepted /\ UNCHANGED vars

Next == Close \/ Watermark \/ Revoke
        \/ (\E r \in Requests : Accept(r) \/ Retry(r))
        \/ UNCHANGED vars

TypeOK == /\ closed \in BOOLEAN /\ watermark \in BOOLEAN /\ revoked \in BOOLEAN
          /\ accepted \subseteq Requests /\ spent \in 0..Limit
          /\ history \in Seq([id : Requests, closed : BOOLEAN,
                               watermark : BOOLEAN, authorised : BOOLEAN])

WithinLimit == spent <= Limit
NoDuplicateCharge == spent = Cardinality(accepted) /\ Len(history) = spent
ReadyAndAuthorised == \A i \in 1..Len(history) :
  /\ history[i].closed /\ history[i].watermark /\ history[i].authorised

Spec == Init /\ [][Next]_vars
=============================================================================
