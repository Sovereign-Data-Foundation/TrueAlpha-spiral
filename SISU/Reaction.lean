import Lean

/-!
# Abstract partial reaction model

This module contains pure settlement and ledger arithmetic only. It does not
implement admission, escrow release authorization, Ed25519, proof verification,
nonce replay protection, or an allocation digest. Candidate arithmetic is not
authority to modify a real ledger. Amounts are unbounded natural numbers, not
256-bit machine arithmetic. This is not a production conformance kernel and
does not establish cryptographic or 256-bit parity.
-/

namespace SISU.Reaction

structure Share where
  artifactId : String
  bps : Nat
  contested : Bool
  deriving Repr, DecidableEq

structure Payment where
  artifactId : String
  amount : Nat
  deriving Repr, DecidableEq

structure Settlement where
  settled : List Payment
  escrow : List Payment
  legalReserve : Nat
  deriving Repr, DecidableEq

private structure RankedShare where
  artifactId : String
  base : Nat
  remainder : Nat
  contested : Bool
  deriving Repr, DecidableEq

private def before (a b : RankedShare) : Bool :=
  a.remainder > b.remainder ||
    (a.remainder == b.remainder && a.artifactId < b.artifactId)

private def insertRanked (x : RankedShare) : List RankedShare → List RankedShare
  | [] => [x]
  | y :: ys => if before x y then x :: y :: ys else y :: insertRanked x ys

private def rankedShares (pool : Nat) (shares : List Share) : List RankedShare :=
  let entries := shares.map fun s =>
    { artifactId := s.artifactId, base := pool * s.bps / 10000,
      remainder := pool * s.bps % 10000, contested := s.contested : RankedShare }
  entries.foldl (fun acc x => insertRanked x acc) []

/-- Walk the ranking from the head, assigning dust to the first entries and
    head-consing every payment into its corresponding output list. -/
private def allocate : Nat → List RankedShare → Settlement → Settlement
  | _, [], state => state
  | dust, x :: xs, state =>
    let payment : Payment :=
      { artifactId := x.artifactId, amount := x.base + (if dust > 0 then 1 else 0) }
    let next :=
      if x.contested then { state with escrow := payment :: state.escrow }
      else { state with settled := payment :: state.settled }
    allocate (dust - 1) xs next

/-- A BPS sum other than 10000 leaves the entire settlement unchanged. -/
def settle (state : Settlement) (pool : Nat) (shares : List Share) : Settlement :=
  if shares.foldl (fun n s => n + s.bps) 0 == 10000 then
    let ranked := rankedShares pool shares
    let bases := ranked.foldl (fun n s => n + s.base) 0
    allocate (pool - bases) ranked state
  else state

structure EpochLedger where
  r_gross : Nat
  r_legal : Nat
  r_infra : Nat
  r_dist : Nat
  liquid_sum : Nat
  escrow_sum : Nat
  escrow_bal : Nat
  deriving Repr, DecidableEq

/-- Arithmetic bounds alone do not authorize a ledger transition. -/
def ledgerBoundsHold (ledger : EpochLedger) (delta : Nat) : Bool :=
  delta <= ledger.escrow_bal && delta <= ledger.escrow_sum && delta <= ledger.r_dist

/-- Compute a candidate ledger, not an authenticated or replay-safe transition.
    All subtraction is guarded by the specified arithmetic bounds. -/
def ledgerCandidate (ledger : EpochLedger) (delta : Nat) (upheld : Bool) :
    Option EpochLedger :=
  if ledgerBoundsHold ledger delta then
    if upheld then
      some { ledger with
        r_legal := ledger.r_legal + delta
        r_dist := ledger.r_dist - delta
        escrow_sum := ledger.escrow_sum - delta
        escrow_bal := ledger.escrow_bal - delta }
    else
      some { ledger with
        liquid_sum := ledger.liquid_sum + delta
        escrow_sum := ledger.escrow_sum - delta
        escrow_bal := ledger.escrow_bal - delta }
  else none

structure EpochLedger64 where
  r_gross : UInt64
  r_legal : UInt64
  r_infra : UInt64
  r_dist : UInt64
  liquid_sum : UInt64
  escrow_sum : UInt64
  escrow_bal : UInt64
  deriving Repr, DecidableEq

/-- Guard the gross-times-1500 intermediate and every converted field; no
    bounded-arithmetic equivalence or 256-bit bridge is asserted. -/
def toUInt64Ledger (l : EpochLedger) : Option EpochLedger64 :=
  let limit := 2 ^ 64
  if l.r_gross * 1500 < limit && l.r_gross < limit &&
      l.r_legal < limit && l.r_infra < limit && l.r_dist < limit &&
      l.liquid_sum < limit && l.escrow_sum < limit && l.escrow_bal < limit then
    some {
      r_gross := UInt64.ofNat l.r_gross
      r_legal := UInt64.ofNat l.r_legal
      r_infra := UInt64.ofNat l.r_infra
      r_dist := UInt64.ofNat l.r_dist
      liquid_sum := UInt64.ofNat l.liquid_sum
      escrow_sum := UInt64.ofNat l.escrow_sum
      escrow_bal := UInt64.ofNat l.escrow_bal }
  else none

def fromUInt64Ledger (l : EpochLedger64) : EpochLedger :=
  { r_gross := l.r_gross.toNat, r_legal := l.r_legal.toNat,
    r_infra := l.r_infra.toNat, r_dist := l.r_dist.toNat,
    liquid_sum := l.liquid_sum.toNat, escrow_sum := l.escrow_sum.toNat,
    escrow_bal := l.escrow_bal.toNat }

private def emptySettlement : Settlement := { settled := [], escrow := [], legalReserve := 0 }

private def exampleSettlement : Settlement :=
  settle emptySettlement 3
    [{ artifactId := "b", bps := 5000, contested := false },
     { artifactId := "a", bps := 5000, contested := true }]

example : exampleSettlement =
    { settled := [{ artifactId := "b", amount := 1 }],
      escrow := [{ artifactId := "a", amount := 2 }], legalReserve := 0 } := by decide
example : settle emptySettlement 5 [{ artifactId := "x", bps := 9999, contested := false }] =
    emptySettlement := by decide
example : settle emptySettlement 5 [{ artifactId := "x", bps := 10001, contested := false }] =
    emptySettlement := by decide
example : settle emptySettlement 2
    [{ artifactId := "c", bps := 2000, contested := false },
     { artifactId := "b", bps := 4000, contested := false },
     { artifactId := "a", bps := 4000, contested := false }] =
    { settled := [{ artifactId := "c", amount := 0 }, { artifactId := "b", amount := 1 },
        { artifactId := "a", amount := 1 }], escrow := [], legalReserve := 0 } := by decide

private def boundedSettlementCheck : Bool :=
  (List.range 8).all fun pool =>
    [0, 1000, 3333, 5000, 10000].all fun bps =>
      let result := settle emptySettlement pool
        [{ artifactId := "a", bps := bps, contested := true },
         { artifactId := "b", bps := 10000 - bps, contested := false }]
      result.escrow.length == 1 && result.settled.length == 1 &&
        (result.escrow ++ result.settled).foldl (fun n p => n + p.amount) 0 == pool

example : boundedSettlementCheck = true := by decide
private def testLedger : EpochLedger :=
  { r_gross := 10, r_legal := 1, r_infra := 2, r_dist := 7,
    liquid_sum := 2, escrow_sum := 5, escrow_bal := 5 }

example : ledgerCandidate testLedger 3 true =
    some {
      r_gross := 10
      r_legal := 4
      r_infra := 2
      r_dist := 4
      liquid_sum := 2
      escrow_sum := 2
      escrow_bal := 2 } := by decide
example : ledgerCandidate testLedger 3 false =
    some {
      r_gross := 10
      r_legal := 1
      r_infra := 2
      r_dist := 7
      liquid_sum := 5
      escrow_sum := 2
      escrow_bal := 2 } := by decide
example : ledgerCandidate testLedger 6 true = none := by decide
example : ledgerBoundsHold { testLedger with escrow_bal := 2 } 3 = false := by decide
example : ledgerBoundsHold { testLedger with escrow_sum := 2 } 3 = false := by decide
example : ledgerBoundsHold { testLedger with r_dist := 2 } 3 = false := by decide
example : (toUInt64Ledger testLedger).map fromUInt64Ledger = some testLedger := by decide
example : toUInt64Ledger { testLedger with r_legal := 2 ^ 64 } = none := by decide
example : toUInt64Ledger { testLedger with r_infra := 2 ^ 64 } = none := by decide
example : toUInt64Ledger { testLedger with r_dist := 2 ^ 64 } = none := by decide
example : toUInt64Ledger { testLedger with liquid_sum := 2 ^ 64 } = none := by decide
example : toUInt64Ledger { testLedger with escrow_sum := 2 ^ 64 } = none := by decide
example : toUInt64Ledger { testLedger with escrow_bal := 2 ^ 64 } = none := by decide
example : (toUInt64Ledger { testLedger with escrow_bal := 2 ^ 64 - 1 }).map fromUInt64Ledger =
    some { testLedger with escrow_bal := 2 ^ 64 - 1 } := by decide
example : toUInt64Ledger { testLedger with r_gross := 2 ^ 64 / 1500 + 1 } = none := by decide

end SISU.Reaction
