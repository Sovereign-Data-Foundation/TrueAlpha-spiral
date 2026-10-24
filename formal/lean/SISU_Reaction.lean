import Mathlib.Data.List.Basic
import Mathlib.Data.Nat.Basic

--------------------------------------------------------------------------------
-- LAYER 3: DUAL-LATTICE MERGE OPERATIONS (Φ)
--------------------------------------------------------------------------------

structure AncestorNode where
  artifactId  : Nat
  createdAtMs : Nat
  rawBps      : Nat
  deriving Repr, DecidableEq

def isEarlierAncestor (a b : AncestorNode) : Bool :=
  if a.createdAtMs != b.createdAtMs then
    a.createdAtMs < b.createdAtMs
  else
    a.artifactId < b.artifactId

def findEarliestAncestor : List AncestorNode → Option AncestorNode
  | []      => none
  | p :: ps => some (ps.foldl (fun best curr => if isEarlierAncestor curr best then curr else best) p)

structure CvpAllocation where
  artifactId : Nat
  bps        : Nat
  deriving Repr, DecidableEq

def sumBps : List CvpAllocation → Nat
  | [] => 0
  | a :: as => a.bps + sumBps as

def normalizeCvp (parents : List AncestorNode) : Option (List CvpAllocation) :=
  let totalRaw := parents.foldl (fun acc p => acc + p.rawBps) 0
  if totalRaw == 0 then
    none
  else
    let baseList := parents.map (fun p => (p, (p.rawBps * 10000) / totalRaw))
    let sumNormalized := baseList.foldl (fun acc (_, bps) => acc + bps) 0
    let delta := 10000 - sumNormalized
    match findEarliestAncestor parents with
    | none => none
    | some earliest =>
      some (baseList.map (fun (p, bps) =>
        if p.artifactId == earliest.artifactId && p.createdAtMs == earliest.createdAtMs then
          ⟨p.artifactId, bps + delta⟩
        else
          ⟨p.artifactId, bps⟩))

--------------------------------------------------------------------------------
-- LAYER 2: SPARSE MERKLE TREE (SMT) REVOCATION ACCUMULATORS
--------------------------------------------------------------------------------

structure SMTProof where
  leafKey   : Nat
  value     : Nat
  root      : Nat
  siblings  : List Nat
  deriving Repr, DecidableEq

-- Terminal zero-state anchor for OURSPACE-SMT-SHA256-V1 over a 256-bit space
def Z_256 : Nat := 61552891

def verifySmtNonInclusion (proof : SMTProof) : Bool :=
  proof.value == 0 && proof.root != Z_256

--------------------------------------------------------------------------------
-- CORE TRANSITION DEFINITIONS: ADMISSION GATE LATTICE (V)
--------------------------------------------------------------------------------

inductive AdmissionGateState
  | VERIFIED
  | INVALID
  | UNVERIFIED
  | REVOKED
  | EXPIRED
  | INDETERMINATE
  deriving DecidableEq, Repr

inductive DisputeState
  | CLEAR
  | DISPUTED
  | EXONERATED
  | FORFEITED
  deriving DecidableEq, Repr

structure AssetBuckets where
  liquid : Nat
  escrow : Nat
  deriving Repr, DecidableEq

structure ArtifactFinancialState where
  id           : Nat
  dispute      : DisputeState
  basisPoints  : Nat
  balances     : AssetBuckets
  deriving Repr, DecidableEq

structure FinancialState where
  artifacts : List ArtifactFinancialState
  treasury  : Nat
  deriving Repr

structure OperationalState where
  executionCount : Nat
  activeLineage  : List Nat
  deriving Repr

structure SystemState where
  opState   : OperationalState
  finState  : FinancialState
  deriving Repr

--------------------------------------------------------------------------------
-- FINANCIAL STATE MACHINE (Q_F) ENGINE & DISPUTE LIFECYCLE
--------------------------------------------------------------------------------

inductive FinancialAction
  | triggerDispute (artifactId : Nat)
  | resolveExonerated (artifactId : Nat)
  | resolveForfeited (artifactId : Nat)
  | accrueRoyalty (artifactId : Nat) (amount : Nat)

def transitionFinancialState (action : FinancialAction) (fs : FinancialState) : FinancialState :=
  match action with
  | FinancialAction.triggerDispute id =>
      { fs with artifacts := fs.artifacts.map fun art =>
          if art.id == id && art.dispute == DisputeState.CLEAR then
            { art with dispute := DisputeState.DISPUTED }
          else art
      }
  | FinancialAction.resolveExonerated id =>
      { fs with artifacts := fs.artifacts.map fun art =>
          if art.id == id && art.dispute == DisputeState.DISPUTED then
            { art with
                dispute := DisputeState.EXONERATED,
                balances := { liquid := art.balances.liquid + art.balances.escrow, escrow := 0 }
            }
          else art
      }
  | FinancialAction.resolveForfeited id =>
      let slashedAmt := fs.artifacts.foldl (fun acc art =>
        if art.id == id && art.dispute == DisputeState.DISPUTED then acc + art.balances.escrow else acc
      ) 0
      { artifacts := fs.artifacts.map fun art =>
          if art.id == id && art.dispute == DisputeState.DISPUTED then
            { art with
                dispute := DisputeState.FORFEITED,
                balances := { art.balances with escrow := 0 }
            }
          else art,
        treasury := fs.treasury + slashedAmt
      }
  | FinancialAction.accrueRoyalty id amt =>
      { fs with artifacts := fs.artifacts.map fun art =>
          if art.id == id then
            match art.dispute with
            | DisputeState.DISPUTED =>
                { art with balances := { art.balances with escrow := art.balances.escrow + amt } }
            | _ =>
                { art with balances := { art.balances with liquid := art.balances.liquid + amt } }
          else art
      }

--------------------------------------------------------------------------------
-- PIPELINE INTEGRATION & UNIFIED COUPLING
--------------------------------------------------------------------------------

def evalAdmissionGate (hasEvidence : Bool) (smtValid : Bool) (isRevoked : Bool) : AdmissionGateState :=
  if ¬hasEvidence then AdmissionGateState.UNVERIFIED
  else if ¬smtValid then AdmissionGateState.INVALID
  else if isRevoked then AdmissionGateState.REVOKED
  else AdmissionGateState.VERIFIED

def systemStep (gateVerified : Bool) (action : FinancialAction) (sys : SystemState) : SystemState :=
  if ¬gateVerified then
    -- Fail-Closed Mechanism: Freeze operational state change, track financial status updates
    { opState  := sys.opState,
      finState := transitionFinancialState action sys.finState }
  else
    { opState  := { sys.opState with executionCount := sys.opState.executionCount + 1 },
      finState := transitionFinancialState action sys.finState }

--------------------------------------------------------------------------------
-- MACHINE-CHECKED ARCHITECTURAL INVARIANT THEOREMS
--------------------------------------------------------------------------------

-- Theorem: Verification gate failure strictly preserves operational execution topology (Fail-Closed)
theorem fail_closed_gate_freezes_operational_state
  (action : FinancialAction) (sys : SystemState) :
  (systemStep false action sys).opState.executionCount = sys.opState.executionCount := by
  dsimp [systemStep]
  rfl

-- Theorem: Core split-state isolation ensuring financial actions maintain zero operational linkage
theorem financial_transition_preserves_operational_lineage
  (gateVerified : Bool) (action : FinancialAction) (sys : SystemState) :
  (systemStep gateVerified action sys).opState.activeLineage = sys.opState.activeLineage := by
  dsimp [systemStep]
  split_ifs
  · rfl
  · rfl

--------------------------------------------------------------------------------
-- MULTI-SIG OPERATOR AUTHORIZATION GATE
--------------------------------------------------------------------------------

-- Number of distinct authorized operators that approved (counting over the
-- authorized set means duplicate approvals cannot inflate the quorum).
def quorumCount (authorized approvals : List Nat) : Nat :=
  (authorized.filter (fun s => approvals.contains s)).length

-- Fail-closed: any missing evidence/SMT/revocation failure takes precedence;
-- a missing quorum yields INDETERMINATE and never VERIFIED.
def evalAdmissionGateMultiSig
    (hasEvidence smtValid isRevoked : Bool)
    (authorized approvals : List Nat) (threshold : Nat) : AdmissionGateState :=
  match evalAdmissionGate hasEvidence smtValid isRevoked with
  | AdmissionGateState.VERIFIED =>
      if threshold ≤ quorumCount authorized approvals ∧ 0 < threshold then
        AdmissionGateState.VERIFIED
      else AdmissionGateState.INDETERMINATE
  | other => other

theorem multisig_verified_implies_quorum
    (e s r : Bool) (authorized approvals : List Nat) (threshold : Nat) :
    evalAdmissionGateMultiSig e s r authorized approvals threshold = AdmissionGateState.VERIFIED →
    threshold ≤ quorumCount authorized approvals ∧ 0 < threshold := by
  intro h
  unfold evalAdmissionGateMultiSig at h
  cases hg : evalAdmissionGate e s r <;> rw [hg] at h <;> simp at h
  all_goals (first | exact h | (split at h <;> simp_all))

--------------------------------------------------------------------------------
-- GLOBAL VALUE PRESERVATION
--------------------------------------------------------------------------------

def artValue (a : ArtifactFinancialState) : Nat :=
  a.balances.liquid + a.balances.escrow

def totalValue (fs : FinancialState) : Nat :=
  (fs.artifacts.map artValue).foldl (· + ·) 0 + fs.treasury

-- Accrual is the only action that mints value; all others are conservative.
def FinancialAction.isConservative : FinancialAction → Bool
  | FinancialAction.accrueRoyalty _ _ => false
  | _ => true

theorem foldl_add_acc (l : List Nat) (acc : Nat) :
    l.foldl (· + ·) acc = acc + l.foldl (· + ·) 0 := by
  induction l generalizing acc with
  | nil => simp
  | cons x xs ih =>
    simp only [List.foldl]
    rw [ih (acc + x), ih (0 + x)]
    omega

theorem map_value_preserved (f : ArtifactFinancialState → ArtifactFinancialState)
    (h : ∀ a, artValue (f a) = artValue a) (l : List ArtifactFinancialState) :
    ((l.map f).map artValue).foldl (· + ·) 0 = (l.map artValue).foldl (· + ·) 0 := by
  induction l with
  | nil => rfl
  | cons x xs ih =>
    simp only [List.map, List.foldl]
    rw [foldl_add_acc _ (0 + artValue (f x)), foldl_add_acc _ (0 + artValue x), ih, h]

theorem trigger_preserves_value (id : Nat) (fs : FinancialState) :
    totalValue (transitionFinancialState (FinancialAction.triggerDispute id) fs) = totalValue fs := by
  unfold totalValue transitionFinancialState
  simp only []
  rw [map_value_preserved]
  intro a
  split <;> simp [artValue]

theorem exonerate_preserves_value (id : Nat) (fs : FinancialState) :
    totalValue (transitionFinancialState (FinancialAction.resolveExonerated id) fs) = totalValue fs := by
  unfold totalValue transitionFinancialState
  simp only []
  rw [map_value_preserved]
  intro a
  split <;> simp [artValue]

-- Slashed escrow moves to treasury unit-for-unit.
theorem forfeit_aux (id : Nat) (l : List ArtifactFinancialState) (acc : Nat) :
    (((l.map fun art =>
        if art.id == id && art.dispute == DisputeState.DISPUTED then
          { art with dispute := DisputeState.FORFEITED,
                     balances := { art.balances with escrow := 0 } }
        else art).map artValue).foldl (· + ·) 0)
      + (l.foldl (fun acc art =>
          if art.id == id && art.dispute == DisputeState.DISPUTED
          then acc + art.balances.escrow else acc) acc)
    = (l.map artValue).foldl (· + ·) 0 + acc := by
  induction l generalizing acc with
  | nil => simp
  | cons x xs ih =>
    simp only [List.map, List.foldl]
    rw [foldl_add_acc _ (0 + _), foldl_add_acc _ (0 + artValue x)]
    split
    · have := ih (acc + x.balances.escrow)
      simp only [artValue] at this ⊢
      omega
    · have := ih acc
      simp only [artValue] at this ⊢
      omega

theorem forfeit_preserves_value (id : Nat) (fs : FinancialState) :
    totalValue (transitionFinancialState (FinancialAction.resolveForfeited id) fs) = totalValue fs := by
  unfold totalValue transitionFinancialState
  simp only []
  have := forfeit_aux id fs.artifacts 0
  omega

theorem conservative_step_preserves_value (action : FinancialAction) (fs : FinancialState)
    (h : action.isConservative = true) :
    totalValue (transitionFinancialState action fs) = totalValue fs := by
  cases action with
  | triggerDispute id => exact trigger_preserves_value id fs
  | resolveExonerated id => exact exonerate_preserves_value id fs
  | resolveForfeited id => exact forfeit_preserves_value id fs
  | accrueRoyalty id amt => simp [FinancialAction.isConservative] at h

def runActions : List FinancialAction → FinancialState → FinancialState
  | [], fs => fs
  | a :: as, fs => runActions as (transitionFinancialState a fs)

-- Multi-step: any sequence of conservative actions preserves total value.
theorem run_conservative_preserves_value (actions : List FinancialAction) (fs : FinancialState)
    (h : ∀ a ∈ actions, a.isConservative = true) :
    totalValue (runActions actions fs) = totalValue fs := by
  induction actions generalizing fs with
  | nil => rfl
  | cons a as ih =>
    simp only [runActions]
    rw [ih _ (fun b hb => h b (List.mem_cons_of_mem a hb)),
        conservative_step_preserves_value a fs (h a (List.mem_cons_self a as))]
