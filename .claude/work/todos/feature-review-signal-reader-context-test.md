# Feature: review-signal should test lines against a reader who was not in the drafting conversation

**Status:** OPEN
**Priority:** medium
**Created:** 2026-09-24
**Source:** routing note in the review-voice round-three plan (2026-09-22-001)

## The problem

Three rounds of live use on a set of deliverables surfaced documents leaning on the drafting
conversation's private vocabulary ("taught frame," "prioritization machinery," "the concrete
skill"). The intended reader, who was not in the drafting conversation, cannot parse those
lines. This is a clarity defect a human consultant also commits, not an AI-voice tell, so it
was routed here rather than into `review-voice`.

## Shape of a fix

A reader-context test in the RENT pass: "would the named reader, who has not seen the drafting
conversation, parse this line?" A line that fails is a Relevance or Traction failure with a
specific cause, and the fix is the explanation register already in `review-voice`'s rewrite
guidance (say it the way you would answer "what does this mean?" aloud).

## Not in scope

Do not add this to `review-voice`. The two lenses are adversarial by design, and this one is a
signal question.
