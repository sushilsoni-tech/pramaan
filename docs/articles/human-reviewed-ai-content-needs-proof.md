# Human-Reviewed AI Content Needs Evidence, Not Just a Promise

Many small teams now use AI to draft, summarize, research, edit, and prepare written work.

That is not the problem.

The problem appears later, when the work is handed to someone else and described with a sentence like:

> This was human reviewed.

That sentence is becoming important. Clients hear it. Editors hear it. Reviewers hear it. Customers hear it. But in most workflows, it is still only a promise. There is no small, portable record that shows what file was reviewed, what AI contributed, whether review was complete or partial, and who accepted responsibility.

Pramaan is an open-source experiment for that narrow gap.

It does not try to detect AI writing. It does not judge whether the content is true. It does not certify legal compliance. It does not prove that every real-world action was recorded.

Instead, Pramaan creates a signed responsibility record for one finished file.

That record can say:

- this is the exact final file hash;
- this is what AI helped with;
- this is whether human review was complete, partial, or absent;
- this is who accepted responsibility;
- this is the public key that signed the record;
- this is whether the signed bundle still verifies later.

The recipient can then verify the record independently on their own machine. For identity trust, the recipient should compare the bundle's signer fingerprint against a fingerprint received through a separate trusted channel.

## Why This Matters For Small Teams

Large organisations may eventually buy governance platforms, connect identity systems, and enforce audit workflows across every tool.

Small teams do not start there.

A small content studio, research writer, AI-assisted proposal shop, grant writer, technical writer, or responsible AI consultant often needs something much lighter:

> I used AI, a human reviewed the final work, and here is the record for this specific deliverable.

That is the first wedge for Pramaan.

The goal is not to create bureaucracy. The goal is to make a human-review claim inspectable.

## What Pramaan Does

Pramaan runs locally.

The current Create Record wizard opens on `127.0.0.1` with:

```powershell
pramaan wizard
```

A producer selects a final file, describes the AI contribution, declares whether human review was complete, partial, or absent, and names the person or entity accepting responsibility.

Pramaan then creates a signed bundle and verifies it immediately.

The bundle can be sent to another person. That person can unzip it and run:

```powershell
pramaan verify <bundle-folder>
```

They get a plain PASS or FAIL, plus a report explaining what passed, what failed, and what remains outside Pramaan's assurance boundary.

## What Pramaan Does Not Prove

This boundary matters.

Pramaan does not prove that the underlying content is true.

It does not prove that the human review was good.

It does not prove the named reviewer is who they say they are. In the current editorial profile, reviewer identity is a producer-supplied assertion, and the signature binds the record to the producer's key, not to a separate reviewer-held key.

It does not prove legal, regulatory, editorial, or academic compliance.

It does not provide trusted timestamping by itself.

It does not prove the producer recorded every real-world action.

It proves something smaller but still useful:

> This signed record has not changed, it refers to this final file, and it satisfies or fails the declared checks.

That smaller claim is the product.

## Why Open Source

If the product is about trust, the verifier should not have to trust a private black box.

Pramaan is open source so a reviewer can inspect how records are built and how verification decisions are made. The sample bundles are included so someone can try verification before creating a record of their own.

There is one PASS sample and one FAIL sample:

```powershell
git clone https://github.com/sushilsoni-tech/pramaan.git
cd pramaan
python -m pip install .
pramaan verify samples/editorial-pass
pramaan verify samples/editorial-fail-missing-reviewer
```

The PASS sample contains a complete declared review record.

The FAIL sample has intact signed files, but it fails because substantive human review and a responsible person are missing.

That distinction is important. Pramaan is not a badge generator. It is allowed to say that a signed record is intact but the declared review is not satisfied.

## Who Should Try It

Pramaan is most useful to people who already make a public or client-facing human-review promise:

- AI-assisted content studios;
- SEO and editorial agencies;
- freelance researchers or writers;
- grant and proposal writers;
- technical writers;
- responsible AI consultants;
- small teams sending AI-assisted written deliverables to someone else.

If nobody ever asks you to explain or evidence human review, Pramaan may be unnecessary.

If your clients already ask what AI contributed, who reviewed the work, and who is accountable, Pramaan may be a useful primitive.

## The Open Question

The question is not whether AI-assisted work will continue.

It will.

The question is whether "human reviewed" remains an unverifiable phrase, or becomes something a second person can inspect.

Pramaan is a small open-source attempt at the second path.

Source: https://github.com/sushilsoni-tech/pramaan
