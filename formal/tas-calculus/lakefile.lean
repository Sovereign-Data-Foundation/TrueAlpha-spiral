import Lake
open Lake DSL

package «tas_calculus» where
  version := v!"0.1.0"
  keywords := #["formal-methods", "state-machine", "tas-calculus"]
  leanOptions := #[
    ⟨`autoImplicit, false⟩,
    ⟨`relaxedAutoImplicit, false⟩
  ]

require mathlib from git
  "https://github.com/leanprover-community/mathlib4.git" @ "v4.16.0"

@[default_target]
lean_lib «TASCalculus» where
  roots := #[`TASCalculus]
