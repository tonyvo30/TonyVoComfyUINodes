## Tony Vo ComfyUI Nodes

# Keyword LoRAs
Apply a LoRA only when its keywords appear in the prompt. Useful for LoRAs that teach one concept (a pose, an outfit, a style) but shift the whole model when loaded: they stay off until the prompt asks for them. Character LoRAs are selected the same way and passed to a dedicated image-only character loader.

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

### Keyword Character
Defines a character selected by keywords, the same `match_any` / `require_all` / `exclude` logic as the rules. Only one character is selected per prompt: the first that matches. When selected, its trigger words are appended to the prompts and its LoRA and strength are passed out of **Apply Keyword LoRAs** for a dedicated character loader, e.g. [Krea2T Character LoRA — Image Only](https://github.com/capitan01R/ComfyUI-Krea2T-Enhancer#character-lora--image-only), which applies the character LoRA to image tokens only. Apply Keyword LoRAs never loads the character's LoRA itself, so a rule or inline tag for it does not apply it a second time.

| Input | Meaning |
| --- | --- |
| `lora_name` | Character LoRA. Passed out of Apply Keyword LoRAs for the character loader. |
| `strength` | Character LoRA strength for the character loader. |
| `match_any` | Comma separated. The character is selected when any of these appear. |
| `require_all` | Comma separated. Every one of these must also appear. |
| `exclude` | Comma separated. Not selected if any of these appear. |
| `positive_append` / `negative_append` | Comma separated words (e.g. trigger words) appended to the prompts on a selection. |

Chain characters through `previous_characters`. Characters are checked before the rules, so a rule can match on a selected character's trigger word: e.g. a character appends `cristyren` and a later refusal-reduction rule matches on `cristyren`.

### Apply Keyword LoRAs
Takes the model, CLIP, prompts, rules and characters, and outputs the patched model and CLIP, the final prompts and a report of what was applied or skipped and why.

The `characters` input takes a chain of Keyword Character nodes. `character_override` forces the selection: `auto` picks the character by keywords, `none` disables characters, and a LoRA name forces the character that uses it (or a bare strength-1 selection if no Character node uses it). The selected character's trigger words are appended to the prompts, and its LoRA, strength and on/off state are passed out on `character_lora`, `character_strength` and `character_enabled`. When no character is selected the LoRA name is empty and `character_enabled` is false, so the character loader stays bypassed.

The positive prompt can also contain inline tags, which are applied and removed from the text:
`<lora:name>`, `<lora:name:strength>` or `<lora:name:model_strength:clip_strength>`. `name` can be the file name or the path inside the loras folder, with or without extension.

Each LoRA is applied at most once; the first inline tag or rule that applies it wins.

### Character LoRAs with Krea2T
Wire the three character outputs of Apply Keyword LoRAs into [Krea2T Character LoRA — Image Only](https://github.com/capitan01R/ComfyUI-Krea2T-Enhancer#character-lora--image-only):

```
Krea2 model → Apply Keyword LoRAs → other LoRA loaders → Krea2T Character LoRA → sampler
                     character_lora → lora_name
                     character_strength → strength_model
                     character_enabled → enabled
```

The character's trigger words are already in the `positive` output, so nothing else is needed to prompt the character. The character's LoRA is loaded only by the Krea2T node, so a rule, an inline tag, or a Keyword Character override all land on the same image-only path.

### Keyword Match
Outputs `matched` (true/false) and a `reason` using the same `match_any` / `require_all` / `exclude` logic as the rules. Connect `matched` to another node's `enabled` input to switch it on by keyword. Feed `text` from the `positive` output of Apply Keyword LoRAs so words added by rules count. Character selection no longer needs this: Apply Keyword LoRAs passes the selected character directly to the character loader.

### Tests
```
python -m unittest discover tests
```
