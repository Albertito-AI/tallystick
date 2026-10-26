--------------------------- MODULE Settlement ---------------------------
EXTENDS Naturals, Integers

CONSTANTS MaxCount, MaxRevision, Threshold
VARIABLES revision, count, closure, official, correctionClosed, finalised,
          result, resultRevision, resultCount, lockedRevision

vars == <<revision, count, closure, official, correctionClosed, finalised,
          result, resultRevision, resultCount, lockedRevision>>

Init == /\ revision = 0
        /\ count = 0
        /\ closure = -1
        /\ official = FALSE
        /\ correctionClosed = FALSE
        /\ finalised = FALSE
        /\ result = "pending"
        /\ resultRevision = -1
        /\ resultCount = -1
        /\ lockedRevision = -1

Observe(n) == /\ ~finalised /\ ~correctionClosed
              /\ revision < MaxRevision
              /\ n \in 0..MaxCount
              /\ revision' = revision + 1
              /\ count' = n
              /\ closure' = -1
              /\ official' = FALSE
              /\ result' = "pending"
              /\ resultRevision' = -1
              /\ resultCount' = -1
              /\ UNCHANGED <<correctionClosed, finalised, lockedRevision>>

Confirm == /\ ~official /\ ~finalised
           /\ official' = TRUE
           /\ UNCHANGED <<revision, count, closure, correctionClosed,
                          finalised, result, resultRevision, resultCount,
                          lockedRevision>>

DeclareClosure(n) == /\ ~finalised /\ official
                     /\ n \in 0..MaxCount
                     /\ closure' = n
                     /\ result' = "pending"
                     /\ resultRevision' = -1
                     /\ resultCount' = -1
                     /\ UNCHANGED <<revision, count, official,
                                    correctionClosed, finalised, lockedRevision>>

Settle == /\ official /\ closure = count
          /\ result' = IF count >= Threshold THEN "over" ELSE "under"
          /\ resultRevision' = revision
          /\ resultCount' = count
          /\ UNCHANGED <<revision, count, closure, official,
                         correctionClosed, finalised, lockedRevision>>

CloseCorrection == /\ ~correctionClosed
                   /\ correctionClosed' = TRUE
                   /\ UNCHANGED <<revision, count, closure, official,
                                  finalised, result, resultRevision,
                                  resultCount, lockedRevision>>

Finalise == /\ correctionClosed /\ ~finalised
            /\ result # "pending" /\ resultRevision = revision
            /\ official /\ closure = count
            /\ finalised' = TRUE
            /\ lockedRevision' = revision
            /\ UNCHANGED <<revision, count, closure, official,
                           correctionClosed, result, resultRevision, resultCount>>

Next == (\E n \in 0..MaxCount : Observe(n) \/ DeclareClosure(n))
        \/ Confirm \/ Settle \/ CloseCorrection \/ Finalise
        \/ UNCHANGED vars

TypeOK == /\ revision \in 0..MaxRevision
          /\ count \in 0..MaxCount
          /\ closure \in -1..MaxCount
          /\ official \in BOOLEAN /\ correctionClosed \in BOOLEAN
          /\ finalised \in BOOLEAN
          /\ result \in {"pending", "over", "under"}
          /\ resultRevision \in -1..MaxRevision
          /\ resultCount \in -1..MaxCount
          /\ lockedRevision \in -1..MaxRevision

CompleteSettlement == result # "pending" =>
  /\ official /\ closure = count
  /\ resultRevision = revision /\ resultCount = count
  /\ (result = "over") = (count >= Threshold)

Finality == finalised =>
  /\ correctionClosed /\ lockedRevision = revision
  /\ result # "pending" /\ resultRevision = revision

Spec == Init /\ [][Next]_vars
=============================================================================
