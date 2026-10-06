## Tony Vo ComfyUI Nodes

# Keyword LoRAs
Apply a LoRA only when its keywords appear in the prompt. Useful for LoRAs that teach one concept (a pose, an outfit, a style) but shift the whole model when loaded: they stay off until the prompt asks for them. No other custom nodes are required.

### Keyword LoRA Rule
One rule per LoRA. Chain rules through `previous_rules` and connect the last one to **Apply Keyword LoRAs**.

| Input | Meaning |
| --- | --- |
| `lora_name` | LoRA to apply. `None` makes a rule that only edits the prompt text. |
| `strength_model` / `strength_clip` | LoRA strengths. |
| `match_any` | Comma separated. Matches when any of these appear. |
| `require_all` | Comma separated. Every one of these must also appear. |
| `exclude` | Comma separated. No match if any of these appear. |
| `positive_append` / `negative_append` | Comma separated words (e.g. trigger words) added to the prompts on a match. Words already present are skipped. |

Matching is case-insensitive and whole-word (`cat` does not match `category`). Spaces in a keyword also match underscores or no space, so `chicken jockey` matches `chicken_jockey` and `chickenjockey`.

Rules are evaluated in chain order and each rule sees the words added by the rules before it, so one rule can set off another. For example, a clothing rule appends its trigger word and a later texture rule matches on that trigger word.

### Apply Keyword LoRAs
Takes the model, CLIP, prompts and rules, and outputs the patched model and CLIP, the final prompts and a report of what was applied or skipped and why.

The positive prompt can also contain inline tags, which are applied and removed from the text:
`<lora:name>`, `<lora:name:strength>` or `<lora:name:model_strength:clip_strength>`. `name` can be the file name or the path inside the loras folder, with or without extension.

Each LoRA is applied at most once; the first inline tag or rule that applies it wins.

### Keyword Match
Outputs `matched` (true/false) and a `reason` using the same `match_any` / `require_all` / `exclude` logic as the rules. Connect `matched` to another node's `enabled` input to switch it on by keyword, e.g. [Krea2T Character LoRA — Image Only](https://github.com/capitan01R/ComfyUI-Krea2T-Enhancer#character-lora--image-only), which has its own way of applying character LoRAs:

```
Krea2 model → Apply Keyword LoRAs → other LoRA loaders → Krea2T Character LoRA (enabled ← Keyword Match) → sampler
```

Feed `text` from the `positive` output of Apply Keyword LoRAs so words added by rules count. For example, a text-only rule matching `cristy` appends the trigger word `cristyren`, and Keyword Match on `cristyren` enables the character loader.

### Tests
```
python -m unittest discover tests
```
