import Mathlib.Data.List.Basic
import Mathlib.Data.Real.Basic
import Mathlib.Tactic

/-!
# TAS Calculus — Reference Operational Semantics

### Orientation Convention
* **Lineages are stored newest-first (stack order):**
  - The head of the list `e :: es` is the most recent event.
  - The tail `es` contains historical events.
  - `step` **prepends** (cons) new events onto the current lineage.
* **Decoder `D` evaluates chronologically:**
  - Evaluates from the oldest event (the tail/nil base case) to the newest event (the head).

### Identity and Proposal Distinctions
* Storing `(x : X) (y : Y)` inside `Event.refuse` ensures that distinct proposals
  $(x, y_1) ≠ (x, y_2)$ produce distinct event values.
* Repeated submissions of identical pairs $(x, y)$ produce equal event values that
  occupy distinct structural positions in the lineage list. Unique per-attempt
  identities (e.g., nonces or timestamps) would require augmenting `Input`.

### Safety Relativity
The theorems `step_preserves_invariant` and `reachable_safe` establish internal
consistency ($O = D(Γ)$) and gate-derivation conformance (`WF`)
relative to abstract parameters `G` and `ω`. Concrete authorization and cryptographic
non-repudiation require concrete instantiations of `G`.
-/

/-- Lineage event alphabet ℰ.
    Both `admit` and `refuse` store `(x, y)` to record the full proposal. -/
inductive Event (X Y Π : Type)
  | admit  (x : X) (y : Y) (π : Π) : Event X Y Π
  | refuse (x : X) (y : Y)         : Event X Y Π

abbrev Lineage (X Y Π : Type) := List (Event X Y Π)

/-- Operational Licensing Map D : Lineage → O.
    Unwinds the newest-first list down to `[] = O₀`, applying `ω` chronologically. -/
def D {O X Y Π : Type} (O₀ : O) (ω : O → X → Y → Π → O) : Lineage X Y Π → O
  | [] => O₀
  | (Event.admit x y π :: es) => ω (D O₀ ω es) x y π
  | (Event.refuse _ _  :: es) => D O₀ ω es

/-- Well-formed lineages generated inductively under the admission gate. -/
inductive WF {O X Y Π : Type} (O₀ : O) (ω : O → X → Y → Π → O)
    (G : O → X → Y → Option Π) : Lineage X Y Π → Prop where
  | empty : WF O₀ ω G []
  | admit (Γ : Lineage X Y Π) (x : X) (y : Y) (π : Π)
      (hWF : WF O₀ ω G Γ)
      (hG  : G (D O₀ ω Γ) x y = some π) :
      WF O₀ ω G (Event.admit x y π :: Γ)
  | refuse (Γ : Lineage X Y Π) (x : X) (y : Y)
      (hWF : WF O₀ ω G Γ)
      (hG  : G (D O₀ ω Γ) x y = none) :
      WF O₀ ω G (Event.refuse x y :: Γ)

/-! ## Parameterized System Configuration -/

structure TASParams where
  O  : Type
  X  : Type
  Y  : Type
  Π  : Type
  O₀ : O
  ω  : O → X → Y → Π → O
  G  : O → X → Y → Option Π

namespace TASParams

variable (P : TASParams)

structure RawState where
  op  : P.O
  lin : Lineage P.X P.Y P.Π

structure Input where
  x : P.X
  y : P.Y

def init : RawState P :=
  ⟨P.O₀, []⟩

/-- Single-step operational transition function.
    Admission applies `ω` and prepends an admit event;
    Refusal holds `op` constant and prepends a refuse event. -/
def step (s : RawState P) (inp : Input P) : RawState P :=
  match P.G s.op inp.x inp.y with
  | some π =>
      { op  := P.ω s.op inp.x inp.y π
        lin := Event.admit inp.x inp.y π :: s.lin }
  | none =>
      { op  := s.op
        lin := Event.refuse inp.x inp.y :: s.lin }

def runTrace : List (Input P) → RawState P → RawState P
  | [], s => s
  | inp :: inps, s => runTrace inps (step P s inp)

/-! ## Safety Invariants -/

def Valid (s : RawState P) : Prop :=
  s.op = D P.O₀ P.ω s.lin

def WellFormed (s : RawState P) : Prop :=
  WF P.O₀ P.ω P.G s.lin

structure Invariant (s : RawState P) : Prop where
  valid : Valid P s
  wf    : WellFormed P s

theorem init_valid : Valid P (init P) := rfl

theorem init_wf : WellFormed P (init P) := WF.empty

theorem init_invariant : Invariant P (init P) :=
  ⟨init_valid P, init_wf P⟩

theorem step_preserves_valid (s : RawState P) (inp : Input P) (hInv : Invariant P s) :
    Valid P (step P s inp) := by
  have hV : s.op = D P.O₀ P.ω s.lin := hInv.valid
  dsimp [step, Valid]
  cases hG : P.G s.op inp.x inp.y with
  | some π =>
      simp [hG, D]
      rw [← hV]
  | none =>
      simp [hG, D]
      exact hV

theorem step_preserves_wf (s : RawState P) (inp : Input P) (hInv : Invariant P s) :
    WellFormed P (step P s inp) := by
  have hV : s.op = D P.O₀ P.ω s.lin := hInv.valid
  have hWF : WF P.O₀ P.ω P.G s.lin := hInv.wf
  dsimp [step, WellFormed]
  cases hG : P.G s.op inp.x inp.y with
  | some π =>
      simp [hG]
      apply WF.admit
      · exact hWF
      · rw [← hV]; exact hG
  | none =>
      simp [hG]
      apply WF.refuse
      · exact hWF
      · rw [← hV]; exact hG

theorem step_preserves_invariant (s : RawState P) (inp : Input P) (hInv : Invariant P s) :
    Invariant P (step P s inp) :=
  ⟨step_preserves_valid P s inp hInv, step_preserves_wf P s inp hInv⟩

theorem runTrace_preserves_invariant (inps : List (Input P)) (s : RawState P)
    (hInv : Invariant P s) :
    Invariant P (runTrace P inps s) := by
  induction inps generalizing s with
  | nil => exact hInv
  | cons inp rest ih =>
    dsimp [runTrace]
    apply ih
    exact step_preserves_invariant P s inp hInv

theorem reachable_safe (inps : List (Input P)) :
    Invariant P (runTrace P inps (init P)) :=
  runTrace_preserves_invariant P inps (init P) (init_invariant P)

end TASParams

/-! ## Explicit StateMachine Structure -/

/-- State machine specification bundling carrier types, execution functions,
    definitional trace laws, and safety proofs. -/
structure StateMachine (P : TASParams) where
  State : Type
  Input : Type
  init : State
  step : State → Input → State
  runTrace : List Input → State → State
  Invariant : State → Prop
  safe_init : Invariant init
  step_safe :
    ∀ s i, Invariant s → Invariant (step s i)
  trace_nil :
    ∀ s, runTrace [] s = s
  trace_cons :
    ∀ i is s, runTrace (i :: is) s = runTrace is (step s i)
  reach_safe :
    ∀ inps, Invariant (runTrace inps init)

/-- Canonical instantiation of `StateMachine` derived from `TASParams`. -/
def StateMachine.ofParams (P : TASParams) : StateMachine P where
  State := TASParams.RawState P
  Input := TASParams.Input P
  init := TASParams.init P
  step := TASParams.step P
  runTrace := TASParams.runTrace P
  Invariant := TASParams.Invariant P
  safe_init := TASParams.init_invariant P
  step_safe := TASParams.step_preserves_invariant P
  trace_nil := by intro s; rfl
  trace_cons := by intro i is s; rfl
  reach_safe := TASParams.reachable_safe P
