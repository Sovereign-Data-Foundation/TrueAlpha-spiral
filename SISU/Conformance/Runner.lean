import Lean
import SISU.Reaction

/-! Shared arithmetic vectors only. This executable does not verify signatures,
proofs, authorization, replay protection, or any actual ledger transition. -/

open Lean SISU.Reaction

namespace SISU.Conformance

open Lean.Parsec Lean.Json.Parser

private partial def objectNoDuplicates (parseValue : Parsec Json) :
    Parsec (RBNode String (fun _ => Json)) := do
  lookahead (fun c => c = '"') "\""
  skip
  let key ← strCore ""
  ws
  lookahead (fun c => c = ':') ":"
  skip
  ws
  let value ← parseValue
  let c ← anyChar
  if c = '}' then
    ws
    return RBNode.singleton key value
  else if c = ',' then
    ws
    let rest ← objectNoDuplicates parseValue
    if (rest.find compare key).isSome then fail s!"duplicate JSON key: {key}"
    return rest.insert compare key value
  else
    fail "unexpected character in object"

private partial def valueNoDuplicates : Parsec Json := do
  let c ← peek!
  if c = '[' then
    skip; ws
    if (← peek!) = ']' then
      skip; ws
      return Json.arr #[]
    else
      return Json.arr (← arrayCore valueNoDuplicates #[])
  else if c = '{' then
    skip; ws
    if (← peek!) = '}' then
      skip; ws
      return Json.obj RBNode.leaf
    else
      return Json.obj (← objectNoDuplicates valueNoDuplicates)
  else if c = '"' then
    skip
    let s ← strCore ""
    ws
    return Json.str s
  else if c = 'f' then
    skipString "false"; ws
    return Json.bool false
  else if c = 't' then
    skipString "true"; ws
    return Json.bool true
  else if c = 'n' then
    skipString "null"; ws
    return Json.null
  else if c = '-' || ('0' ≤ c && c ≤ '9') then
    let n ← num
    ws
    return Json.num n
  else
    fail "unexpected input"

private def parseNoDuplicates (s : String) : Except String Json :=
  let parser : Parsec Json := do
    ws
    let value ← valueNoDuplicates
    eof
    return value
  match parser s.mkIterator with
  | .success _ value => .ok value
  | .error it error => .error s!"offset {repr it.i.byteIdx}: {error}"

private def fields (j : Json) (names : List String) : Except String Unit := do
  let obj ← j.getObj?
  let count := obj.fold (fun n _ _ => n + 1) 0
  if count != names.length then throw "unexpected object fields"
  for name in names do
    let _ ← j.getObjVal? name

private def field (j : Json) (name : String) : Except String Json :=
  j.getObjVal? name

private def natField (j : Json) (name : String) : Except String Nat := do
  (← field j name).getNat?

private def idField (j : Json) (name : String) : Except String String := do
  let s ← (← field j name).getStr?
  if s.isEmpty || !s.toList.all (fun c => c.toNat < 128) then
    throw "expected nonempty ASCII identifier"
  return s

private def parseShare (j : Json) : Except String Share := do
  fields j ["artifact_id", "bps", "contested"]
  let name ← idField j "artifact_id"
  let bps ← natField j "bps"
  let contested ← (← field j "contested").getBool?
  if bps > 10000 then throw "basis points exceed 10000"
  return { artifactId := name, bps := bps, contested := contested }

private def parsePayment (j : Json) : Except String Payment := do
  fields j ["artifact_id", "amount"]
  return { artifactId := ← idField j "artifact_id", amount := ← natField j "amount" }

private def settlement (j : Json) : Except String String := do
  fields j ["id", "pool", "shares", "expected"]
  let id ← idField j "id"
  let pool ← natField j "pool"
  let rawShares ← (← field j "shares").getArr?
  let shares ← rawShares.toList.mapM parseShare
  let limit := 2 ^ 64
  if pool >= limit || shares.isEmpty then throw "invalid pool or shares"
  let ids := shares.map (·.artifactId)
  if ids.eraseDups.length != ids.length then throw "duplicate share identifier"
  if shares.foldl (fun n s => n + s.bps) 0 != 10000 then
    throw "basis points must sum to 10000"
  if shares.any (fun s => pool * s.bps >= limit) then
    throw "settlement intermediate exceeds UInt64"
  let expected ← field j "expected"
  fields expected ["settled", "escrow", "legal_reserve"]
  let settled ← (← (← field expected "settled").getArr?).toList.mapM parsePayment
  let escrow ← (← (← field expected "escrow").getArr?).toList.mapM parsePayment
  let reserve ← natField expected "legal_reserve"
  let wanted : Settlement := { settled := settled, escrow := escrow, legalReserve := reserve }
  let initial : Settlement := { settled := [], escrow := [], legalReserve := 0 }
  let actual := settle initial pool shares
  if actual != wanted then
    throw s!"settlement {id}: expected {repr wanted}, got {repr actual}"
  return id

private def parseLedger (j : Json) : Except String EpochLedger := do
  fields j ["r_gross", "r_legal", "r_infra", "r_dist", "liquid_sum", "escrow_sum", "escrow_bal"]
  return {
    r_gross := ← natField j "r_gross", r_legal := ← natField j "r_legal",
    r_infra := ← natField j "r_infra", r_dist := ← natField j "r_dist",
    liquid_sum := ← natField j "liquid_sum", escrow_sum := ← natField j "escrow_sum",
    escrow_bal := ← natField j "escrow_bal" }

private def uint64Ledger (j : Json) : Except String String := do
  fields j ["id", "ledger", "expected"]
  let id ← idField j "id"
  let ledger ← parseLedger (← field j "ledger")
  let expected ← (← field j "expected").getBool?
  let converted := toUInt64Ledger ledger
  let actual := converted.isSome
  if actual != expected then
    throw s!"uint64_ledger {id}: expected {expected}, got {actual}"
  if let some value := converted then
    if fromUInt64Ledger value != ledger then throw s!"uint64_ledger {id}: round trip mismatch"
  return id

private def runFamily (name : String) (value : Json) : Except String Nat := do
  let runner ← match name with
    | "settlement" => pure settlement
    | "uint64_ledger" => pure uint64Ledger
    | _ => throw s!"unsupported family: {name}"
  let vectors ← value.getArr?
  if vectors.isEmpty then throw s!"empty family: {name}"
  let ids ← vectors.toList.mapM runner
  if ids.eraseDups.length != ids.length then throw s!"duplicate vector id in {name}"
  return ids.length

private def run (data : Json) : Except String String := do
  fields data ["version", "families"]
  if (← (← field data "version").getStr?) != "0.7.0" then throw "invalid version"
  let families ← (← field data "families").getObj?
  let items := families.fold (fun acc name value => (name, value) :: acc) []
  if items.isEmpty then throw "empty families"
  let counts ← items.mapM fun (name, vectors) => do
    let count ← runFamily name vectors
    return s!"{name}={count}"
  return "PASS arithmetic only: " ++ String.intercalate ", " counts

end SISU.Conformance

private def runFile (path : String) : IO UInt32 := do
  try
    let input ← IO.FS.readFile path
    match (SISU.Conformance.parseNoDuplicates input >>= SISU.Conformance.run) with
    | .ok message =>
      IO.println message
      return (0 : UInt32)
    | .error message =>
      IO.eprintln s!"FAIL: {message}"
      return (1 : UInt32)
  catch e =>
    IO.eprintln s!"FAIL: {e}"
    return (1 : UInt32)

def main (args : List String) : IO UInt32 :=
  match args with
  | [] => runFile "tas_vectors_v0_7_0.json"
  | [path] => runFile path
  | _ => do
    IO.eprintln "FAIL: usage: runner [path]"
    return (1 : UInt32)
