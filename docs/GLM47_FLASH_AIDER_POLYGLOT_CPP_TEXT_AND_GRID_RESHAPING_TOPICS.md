# Text And Grid Reshaping Topics For GLM C++ SFT Planning

Status: curriculum-planning taxonomy. This is not a claim that every example
below was evaluated in the Aider benchmark.

The complete GLM-4.7-Flash Modal/Aider C++ evaluation identifies structured
text and grid transformation as an area needing more reliable first-try
implementation. This note names the underlying topics at useful curriculum
granularity. The official Aider tasks remain benchmark holdouts: do not add
them, their tests, their references, or close semantic copies to SFT data.

See `docs/GLM47_FLASH_AIDER_POLYGLOT_CPP_STRUGGLE_CONTEXT.md` for the run
evidence and broader curriculum implications.

## Matrix Orientation And Traversal

These problems retain the values in a rectangular grid while changing the
order in which they are read or the coordinates assigned to them. Correctness
depends on stating the source and destination dimensions, preserving every
cell exactly once, and treating non-square matrices as first-class cases.

- **Transpose / rotate-matrix** — turn cleaned input rows into output columns,
  or map each source coordinate to its transposed destination.
- **Matrix rotation by 90 degrees** — rotate a square matrix clockwise or
  counter-clockwise, with an explicit direction and coordinate mapping.
- **In-place layer rotation** — move the four corresponding positions of each
  square-matrix layer without overwriting a value that has not yet moved.
- **Spiral-matrix traversal** — read a matrix clockwise or counter-clockwise
  by shrinking top, bottom, left, and right boundaries after each side.
- **Spiral-matrix fill** — assign a supplied sequence into a matrix in spiral
  order, including the final center cell or center pair when dimensions meet.
- **Rectangular boundary cases** — preserve correct behavior for one row, one
  column, empty input when the API permits it, and odd versus even dimensions.

The generic row/column transformation capability must remain materially
distinct from every permanent benchmark holdout; it is not a license to
paraphrase an online transpose exercise.

## Symmetric Rendering And Character-Grid Scaling

Rendering tasks turn dimensions, symbols, or a compact character grid into a
visually structured result. A dependable implementation derives each output
row from a clear invariant instead of accumulating ad hoc spaces and symbols.

- **Pattern printing (diamond / triangle)** — generate symmetric character
  rows with specified alignment, width progression, and peak behavior.
- **Centering and padding** — calculate leading, interior, and trailing spaces
  from a declared output width rather than relying on display assumptions.
- **ASCII-art scaling** — enlarge or reduce a character grid while preserving
  its shape, typically by repeating source cells horizontally and source rows
  vertically for integer scale factors.
- **Output-boundary discipline** — preserve intentional blank cells while
  avoiding unintended trailing spaces or final-newline differences when the
  contract makes them observable.
- **Degenerate dimensions** — define zero, one, and even-width behavior
  explicitly rather than allowing loop bounds to select a pattern by accident.

The benchmark's `diamond` exercise is an example of symmetric pattern output
and must remain a holdout.

## Text Reflow And Tabular Reshaping

These transformations reshape a sequence of textual fields while retaining
their content and declared ordering. Robust solutions separate tokenization or
cell parsing from layout, so whitespace and headers do not become accidental
data loss.

- **Word wrap** — greedily or deliberately reflow words into fixed-width lines
  without splitting a word unless the API says to hyphenate or break it.
- **Text justification** — distribute required spaces across inter-word gaps,
  including the remainder policy and distinct final-line behavior.
- **Paragraph normalization** — collapse or preserve input whitespace only as
  the contract requires, while retaining paragraph boundaries and empty lines.
- **Table pivot (rows to columns)** — realign a header and data cells so each
  input field lands under its new row or column label.
- **Table unpivot (columns to rows)** — turn repeated columns into key/value
  records while preserving row identity and missing-cell semantics.
- **Ragged table handling** — reject, pad, or preserve unequal row lengths by
  an explicit policy rather than silently indexing past a row boundary.

The benchmark's `word-count` exercise is related to text tokenization but is
not a substitute for this layout-focused curriculum; it too must remain a
holdout where applicable.

## Grid Interpretation And Region Relabeling

Here the input grid is a diagram or spatial model rather than merely a
container of values. Correctness requires an explicit neighborhood definition,
stable coordinate conventions, and a policy for background, borders, and
disconnected regions.

- **Grid-to-ownership mapping** — read a diagram and attribute each marked
  cell to the appropriate owner, label, or bounded region.
- **Flood fill** — replace one connected region with a new label or character
  without crossing a boundary and without revisiting cells indefinitely.
- **Four- versus eight-neighbor connectivity** — choose orthogonal-only or
  diagonal-inclusive adjacency from the problem contract before traversing.
- **Region measurement** — compute a filled region's area, boundary, or
  components after parsing, while preserving the source grid if the API
  requires a non-mutating result.
- **Maze to graph** — parse walkable cells and exits into vertices and
  adjacency edges, with walls, bounds, and coordinate labels handled
  consistently.
- **Reachability after reshaping** — verify that a transformed map has the
  intended connectivity rather than assuming a visually plausible result is a
  valid graph.

The official Aider holdout `kindergarten-garden` is a related grid-attribution
family and must remain a holdout; do not create a renamed student-to-plot
assignment task.

## Dense, Sparse, And Compressed Grid Representations

These problems change the representation of a grid rather than necessarily
changing the depicted shape. A sound solution establishes a canonical ordering
and validates dimensions before encoding or decoding, so an all-empty row or
repeated run cannot disappear.

- **Sparse-matrix encoding** — convert a dense grid into coordinate/value
  entries, usually omitting a designated default value while retaining shape
  metadata.
- **Sparse-matrix decoding** — reconstruct the dense grid from dimensions and
  coordinate entries, rejecting duplicate or out-of-range coordinates unless a
  merge rule is specified.
- **Run-length image encoding** — compress each grid row as value/count runs,
  preserving row boundaries even when the same value continues visually into
  the next row.
- **Run-length decoding** — expand runs with positive counts and verify that
  every row reaches exactly its declared width.
- **Canonical coordinate order** — define row-major or column-major ordering
  and keep it stable across serialization, comparison, and round trips.
- **Round-trip invariants** — test that decode(encode(grid)) equals the input
  grid and that normalized encodings do not contain adjacent mergeable runs.

## Use In Data Design

Create semantically distinct, licensed tasks that exercise one or more topics
above. Keep source families isolated across splits, retain hidden tests outside
training rows, and apply the repository's contamination and admission gates
before adding any candidate to an SFT release. In particular, do not create
near-copies of the Aider `diamond`, `spiral-matrix`, or
`kindergarten-garden` benchmark exercises; vary the public API, story,
input/output representation, and required edge cases while preserving the
intended curriculum skill.
