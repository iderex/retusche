# Transparency duties for what this service generates

## What this document is

The position on the transparency article of the EU artificial intelligence
regulation, for a service whose whole purpose is to alter photographs. It says
who carries which duty in a self-hosted deployment, which of this service's
outputs are in scope, and what an operator is left holding that this project
cannot hold for them.

It is the analysis. Implementing the marking is issue #70, and nothing in this
document marks anything.

It is not legal advice and it is not a compliance assessment. An operator
running this service in the Union is the one whose deployment is judged, and
the last two sections say exactly which parts of that judgement this project
cannot make for them.

## How to read the claims below

Every quotation from the regulation is read from the text the Publications
Office serves, at the commands in the next section, on the date those commands
were run. Where this document reasons from a quotation rather than quoting, it
says so, and where the reasoning could go the other way, the alternative is
written out beside it rather than left implied.

Nothing here is verified against a running deployment, because there is not yet
a runnable service to deploy. What the tree holds today is in
`docs/legal/data-protection.md` and is not restated.

## What was read, and where

`eur-lex.europa.eu` sits behind a challenge that a command-line fetch cannot
answer, so the text was taken from the Publications Office instead, which
serves the same authenticated act by its CELEX identifier. Read on 2026-08-07:

    curl -sS -L --compressed -H "Accept: application/xhtml+xml" \
      -H "Accept-Language: eng" -o act.html \
      -w "%{http_code} %{size_download}\n" \
      http://publications.europa.eu/resource/celex/32024R1689
    200 1262391

That is Regulation (EU) 2024/1689. It is not the whole of the law in force,
because it has since been amended, and the amending act was read the same way:

    curl -sS -L --compressed -H "Accept: application/xhtml+xml" \
      -H "Accept-Language: eng" -o omnibus.html \
      -w "%{http_code} %{size_download}\n" \
      http://publications.europa.eu/resource/celex/32026R1744
    200 351287

    REGULATION (EU) 2026/1744 OF THE EUROPEAN PARLIAMENT AND OF THE COUNCIL
    of 8 July 2026
    amending Regulations (EU) 2024/1689, (EU) 2018/1139 and (EU) 2023/1230 as
    regards the simplification of the implementation of harmonised rules on
    artificial intelligence (Digital Omnibus on AI)

Published in the Official Journal on 24 July 2026, and its final article says
it enters into force on the third day following publication.

No consolidated text exists for this to be read against. Three plausible
consolidated identifiers were asked for and none resolved:

    for c in 02024R1689-20250802 02024R1689-20260802 02024R1689-20240801; do
      curl -sS -L -o /dev/null -w "%{http_code} $c\n" \
        http://publications.europa.eu/resource/celex/$c
    done
    404 02024R1689-20250802
    404 02024R1689-20260802
    404 02024R1689-20240801

So the reading below is the original act plus the amending act applied by hand,
and that is a place where a mistake would be mine rather than the source's.

## Does the regulation reach this project at all

This project is released under a free and open-source licence, and the
regulation carves such systems out of its scope in Article 2(12):

    12.   This Regulation does not apply to AI systems released under free and
    open-source licences, unless they are placed on the market or put into
    service as high-risk AI systems or as an AI system that falls under
    Article 5 or 50.

The carve-out ends where Article 50 begins, so a system that falls under
Article 50 is inside the regulation however it is licensed. Being free software
removes nothing here.

Article 2 was amended by the Digital Omnibus on AI in three places, its
paragraphs 2 and 7 and a new paragraph 13. Paragraph 12 is not among them, so
the sentence above is the text in force.

## Who is the provider and who is the deployer

The two definitions, from Article 3:

    (3) 'provider' means a natural or legal person, public authority, agency or
    other body that develops an AI system or a general-purpose AI model or that
    has an AI system or a general-purpose AI model developed and places it on
    the market or puts the AI system into service under its own name or
    trademark, whether for payment or free of charge;

    (4) 'deployer' means a natural or legal person, public authority, agency or
    other body using an AI system under its authority except where the AI
    system is used in the course of a personal non-professional activity;

Neither definition was touched by the amending act. Its Article 3 amendments
replace point (14) and insert points (14a) and (14b).

Two supporting definitions decide where the provider role lands. Article 3(9)
makes placing on the market "the first making available of an AI system or a
general-purpose AI model on the Union market", and Article 3(11) makes putting
into service "the supply of an AI system for first use directly to the deployer
or for own use in the Union for its intended purpose".

The position taken here is that in a self-hosted deployment the operator is
both. They put the system into service for their own use, which is the second
limb of Article 3(11), and they then use it under their own authority, which is
Article 3(4). Publishing source code is neither: nothing is made available on
the Union market and nothing is supplied for first use by publishing a
repository.

This is an interpretation and it is stated as one. The alternative reading is
that whoever publishes a working service, even as source, is placing an AI
system on the market and is therefore the provider, with the operator as
deployer on top of that. Two things favour the reading taken here. Article 3(10)
defines making available on the market as supply "in the course of a commercial
activity", which publishing a repository is not, and the whole point of the
Article 2(12) carve-out is that publishing free software is not by itself the
act the regulation attaches obligations to, since otherwise the carve-out would
have nothing to carve.

The consequence of being wrong matters more than the argument, so it is written
plainly. If the alternative reading is right, the provider duty in Article 50(2)
falls on whoever publishes this project as well as on the operator. This project
therefore behaves as though it does: the marking in #70 is built into the
service rather than left to the operator to add, which is what discharging a
provider duty would look like either way. Nothing in this project's position
depends on the interpretation being the favourable one.

There is one exception worth naming because it is the common case for this
software. Article 3(4) excludes use "in the course of a personal
non-professional activity", so somebody editing their own family photographs on
their own machine is not a deployer at all, and the deployer duty in
Article 50(4) does not reach them. The provider duty in Article 50(2) is not
written with that exclusion and does not follow it.

## Which duty falls where

Article 50 lays down four duties, in its paragraphs 1 to 4, and its remaining
three paragraphs govern how they are met rather than adding one. Two of the four
do not reach this project, and saying which and why is part of the position.

Article 50(1) is about systems "intended to interact directly with natural
persons". This is a backend that speaks HTTP to whatever an integration puts in
front of it, and the person editing a photograph is interacting with that
integration. Read as not applicable to this project, and as something the
integration in front of it may still owe. This is a reading rather than a
quotation, and it is the one place in this document where the boundary between
this service and its caller does the work.

Article 50(3) is about emotion recognition and biometric categorisation. This
project does neither, and issue #94 does not contemplate it.

Article 50(2) is the provider duty and it is the one this project is built
around:

    2.   Providers of AI systems, including general-purpose AI systems,
    generating synthetic audio, image, video or text content, shall ensure that
    the outputs of the AI system are marked in a machine-readable format and
    detectable as artificially generated or manipulated. Providers shall ensure
    their technical solutions are effective, interoperable, robust and reliable
    as far as this is technically feasible, taking into account the
    specificities and limitations of various types of content, the costs of
    implementation and the generally acknowledged state of the art, as may be
    reflected in relevant technical standards. This obligation shall not apply
    to the extent the AI systems perform an assistive function for standard
    editing or do not substantially alter the input data provided by the
    deployer or the semantics thereof, or where authorised by law to detect,
    prevent, investigate or prosecute criminal offences.

Article 50(4), first subparagraph, is the deployer duty:

    4.   Deployers of an AI system that generates or manipulates image, audio
    or video content constituting a deep fake, shall disclose that the content
    has been artificially generated or manipulated.

Article 50(5) governs how any of that reaches a person: the information "shall
be provided to the natural persons concerned in a clear and distinguishable
manner at the latest at the time of the first interaction or exposure" and
"shall conform to the applicable accessibility requirements". That sentence is
about a person being told something, which is a surface this project does not
have, and it is the clearest signal that the disclosure half belongs to whoever
shows the picture to somebody.

The Digital Omnibus on AI touches Article 50 in exactly one place, and it is
none of the four paragraphs above. Its item (20) replaces Article 50(7), which
is about codes of practice and is dealt with in the last section of this
document. Paragraphs 1 to 5 are the text as originally published.

That claim is a negative one, so the way it was checked is worth writing down
next to it. The amending act separates an article number from its numeral with
a non-breaking space, so the obvious search finds nothing and reads as an
absence:

    grep -c 'Article 50' omnibus.txt
    0
    grep -c $'Article\u00a050' omnibus.txt
    5

Five lines, of which one is a recital, one is the transitional provision below,
one is the recital explaining the replacement of paragraph 7, one is that
replacement, and the last is Article 50 of Regulation (EU) 2018/1139 in the
second half of the act, which amends civil aviation law and is not this
Article 50 at all.

## Which outputs are in scope

The question this project cannot avoid is the carve-out at the end of
Article 50(2): the duty does not apply "to the extent the AI systems perform an
assistive function for standard editing or do not substantially alter the input
data provided by the deployer or the semantics thereof".

Three operations are planned. Generative fill and canvas extension synthesise
pixels that were never photographed, from a model, and no reading of "standard
editing" covers inventing a piece of a scene. Both are in scope and there is no
argument to make.

Object removal is the one worth reasoning about, and the reasoning is not the
same for every removal. Taking a dust speck off a scan does not alter the
semantics of the photograph and looks exactly like the assistive function the
carve-out describes. Taking a person out of a photograph alters what the
photograph says happened, and the pixels that replace them are generated rather
than recovered. The same endpoint, the same model and the same mask machinery
produce both, and what separates them is the meaning of the region the caller
selected, which is a judgement about the picture that no part of this service
is in a position to make.

So the position is that everything this service produces is marked, and the
carve-out is not relied on for any output. The reasoning is that the carve-out
is written "to the extent" it applies, which makes it a per-output judgement,
and the only route to making that judgement per output would be a rule about
mask area or subject matter that would be wrong in both directions and would
have to be defended each time it was. Marking every output costs an operator
nothing they cannot undo and removes the question.

The alternative position is that a mask below some threshold is standard
editing and need not be marked. It is a defensible reading of the same
sentence, and it is rejected here because the threshold would be invented
rather than derived, not because the reading is unavailable.

One consequence of marking everything is stated rather than left to be
discovered: an output that was in truth outside the duty still carries a mark
saying it was generated, which is an assertion about a photograph that a
downstream tool may act on. That is the direction this project prefers to be
wrong in, and an operator who disagrees has issue #94 to disagree in.

## The dates

Article 113 of the original act says the regulation "shall apply from
2 August 2026", with three exceptions in its third paragraph, for Chapters I
and II, for a named list of later chapters and articles, and for Article 6(1).
Article 50 sits in Chapter IV, which is in none of the three, so it takes the
general date.

The Digital Omnibus on AI amends that third paragraph, replacing its points (a)
and (c) and adding a point (d). None of the replacements reaches Chapter IV, and
the second paragraph carrying 2 August 2026 is not amended at all.

Issue #69 reported that a transitional arrangement for systems already on the
market was under discussion and asked for it to be verified against the
published text. It was adopted. The amending act inserts a new paragraph 4 into
Article 111 of the regulation:

    4.   Providers of AI systems, including general-purpose AI systems,
    generating synthetic audio, image, video or text content, that have been
    placed on the market before 2 August 2026 shall take the necessary steps in
    order to comply with Article 50(2) by 2 December 2026.

Its condition is the part that matters here. The relief reaches systems placed
on the market before 2 August 2026, and this project has not been placed on the
market at all: it has no release, no image an operator can run and no runnable
service. So nothing in this project's history qualifies, and the marking duty
is not one this project can treat as arriving in December. An operator putting
a self-hosted deployment into service now is outside the transitional paragraph
for the same reason.

## What this project cannot discharge

The deployer duty in Article 50(4) is not dischargeable by software, and the
project should not pretend otherwise.

Disclosure under Article 50(4) is an act toward the people who see the content,
performed at the point they see it, in the manner Article 50(5) describes. This
service never meets them. It returns bytes to an integration, which returns
them to a library, which shows them to whoever the operator lets in, and every
step after the first is outside this project. There is no setting that makes
that disclosure happen and no marking that substitutes for it.

Whether a given output constitutes a deep fake is also not a question this
service can answer. That depends on whether the result resembles a real person,
place or event, which is a fact about the photograph and the world rather than
about the request.

What is offered instead, and each of these names the issue that owes it because
none of them exists yet:

The machine-readable mark on every output, #70, which is the provider-side
obligation and is also the evidence an operator needs in order to know which of
their own assets came out of this service.

A record of what was edited, #67, so an operator can answer the question after
the fact for a specific asset rather than by looking at the picture.

The model registry and the licence surface, #38 and #71, because what the
operator has to say about an output depends partly on what produced it.

This document itself, which an operator may quote as the description of what
the software does and does not do.

## What is not decided here

Whether the marking can be switched off is entry 3 of issue #94 and is not
answered in this document.

How the mark is written, in which formats it survives and what it records is
#70.

What a code of practice under Article 50(7) will say. That paragraph is the one
the Digital Omnibus on AI replaced, and the replacement is the text in force:

    7.   The Commission shall encourage and facilitate the drawing up of codes
    of practice at Union level to facilitate the effective implementation of the
    obligations regarding the detection, marking and labelling of artificially
    generated or manipulated content. The Commission, taking utmost account of
    the opinion of the Board, shall assess whether adherence to those codes of
    practice is adequate to ensure compliance with the obligations laid down in
    paragraphs 2 and 4 of this Article, in accordance with the procedure laid
    down in Article 56(6). If it deems the code of practice to be inadequate,
    the Commission may adopt an implementing act specifying common rules for the
    implementation of those obligations in accordance with the examination
    procedure laid down in Article 98(2).

Two changes matter for reading it. The drawing up of codes of practice moved
from the AI Office to the Commission, and the route by which the Commission
approves an adequate code by implementing act is gone, leaving an assessment
instead. The recital explaining the amendment gives the reason, that the codes
"have limited legal effect, and in particular do not grant a presumption of
conformity", so an implementing act to approve one was not strictly necessary.

Whether any such code exists today was not established here. Two candidate
pages on the Commission's own site were fetched on 2026-08-07 and both returned
a not-found page, which shows that those two addresses are wrong and nothing
about whether a code has been drawn up:

    curl -sS -L -o page.html -w "%{http_code}\n" \
      https://digital-strategy.ec.europa.eu/en/policies/ai-act-transparency
    200
    grep -o "<title>[^<]*</title>" page.html
    <title>Page not found | Shaping Europe’s digital future</title>

So this document is written from the regulation alone. A code of practice would
bear directly on the reading of "technically feasible" in Article 50(2) and on
the standard-editing carve-out, which is the ground this document reasons on,
and it should be read again against one when there is one to read.
