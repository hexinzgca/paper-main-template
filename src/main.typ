// No external Typst packages or experiment files are required.
// Always compile with the repository root: typst compile --root . ...
#let meta = json("/project.json")
#set document(title: meta.title, author: meta.authors)
#set page(paper: "a4", margin: (x: 25mm, y: 24mm), numbering: "1")
#set text(font: "Libertinus Serif", size: 11pt, lang: "en")
#set par(justify: true, leading: 0.65em)
#set heading(numbering: "1.1")
#set math.equation(numbering: "(1)")

#align(center)[
  #text(size: 21pt, weight: "bold")[#meta.title]
  #v(0.6em)
  #meta.authors.join(", ")
  #v(0.5em)
  #text(size: 9pt, fill: luma(90))[Manuscript template · replace all instructional text]
]
#v(1em)
#block(inset: 10pt, stroke: 0.5pt + luma(200), width: 100%)[
  *Abstract* #linebreak()
  #meta.abstract
]

#include "sections/01-introduction.typ"
#include "sections/02-methods.typ"
#include "sections/03-results.typ"
#include "sections/04-discussion.typ"

#bibliography("refs.bib", title: "References", style: "ieee")
