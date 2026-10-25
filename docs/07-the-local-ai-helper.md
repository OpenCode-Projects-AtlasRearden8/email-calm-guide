# The local AI helper

This chapter is optional in the way a good kitchen gadget is optional: everything in this manual works without it. But if you've ever wished for "someone to shorten this" or "someone to tell me what this person is actually asking", a small AI running on your own computer is a genuinely useful co-worker — and unlike the cloud kind, it sees nothing you don't hand it, needs no account, and costs nothing per month.

## What "local AI" means, friend version

The big-name chatbots run on other people's servers; your text travels to them. *Local* AI runs as a file on your machine. You download a small model once, and after that it works with the internet unplugged. Your emails go from your inbox to a program on your laptop — and nowhere else.

Two beginner-friendly ways to get one:

- **Ollama** (ollama.com): install it, then run one command like `ollama pull llama3.2:3b` and you have a small model. You talk to it from a terminal or through simple apps.
- **LM Studio**: a point-and-click desktop app with a model-search built in. If terminals aren't your thing, start here.

Both are free, offline after setup, and mentioned here as examples of the approach rather than endorsements of one specific product.

## The four jobs it's actually good at in email

1. **Shortening.** You wrote nine sentences; it proposes three that say the same thing. You accept, tweak, send.
2. **Softening.** Your 11pm "FINE. WHATEVER." becomes something you can actually send. (You still read it first.)
3. **Summarizing long threads.** Twelve messy replies in, ask: *what's decided, what's open, who owes what?*
4. **Finding the ask.** Vague emails ("circling back", "thoughts?") hide their question well. Paste it in and ask what's really being requested.

## Copy-paste prompt recipes

Use these with any local model. Brackets are your fill-ins.

```text
Shorten this email to three sentences, keep the ask and the deadline:
[paste draft]
```

```text
Rewrite this so it sounds warm and normal, not curt or passive-aggressive,
same length or shorter:
[paste draft]
```

```text
Summarize this email thread in five bullets: what is decided,
what is still open, who owes what:
[paste thread]
```

```text
What is this email actually asking me to do, in one sentence:
[paste email]
```

Then always send *your* edited version, not the raw draft. The model is a fast first-draft gremlin, not a mouthpiece.

## The no-fake-brave disclaimer, done briefly

Local AI keeps mail on your machine, which is most of the privacy story. The rest: nobody's model is always right, and you're the one whose name goes on the send. Read before you send — that's not a legal line, it's the actual workflow.

## Pairs with kind-email-crafter-cli

The companion tool kind-email-crafter-cli ties this chapter together: it reads the same `templates/replies/` files from this repo, uses your local model to fill the blanks with draft language, and gives you a plain-text reply to edit and send. Same files as this manual, same blanks — the guide teaches the move, the tool speeds it up, and neither phones home.

> **If you only do one thing:** if you're even slightly curious, install Ollama or LM Studio and ask it to shorten a *made-up* practice email you're not going to send. Two minutes, and you'll know within one email whether this is your kind of tool.
