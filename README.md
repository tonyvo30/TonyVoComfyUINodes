# Tony Vo ComfyUI Nodes

Keyword-triggered LoRA loading and face coverage measurement for ComfyUI. All nodes are in the `TonyVoNodes` category.

| Node | Purpose |
| --- | --- |
| [Keyword LoRA Rule](#keyword-lora-rule) | Applies a LoRA only when its keywords appear in the prompt. |
| [Keyword Character](#keyword-character) | Selects one character LoRA per prompt by keyword. |
| [Apply Keyword LoRAs](#apply-keyword-loras) | Evaluates rules, characters and inline `<lora:...>` tags, and patches the model. |
| [Keyword Match](#keyword-match) | Outputs true when keywords are found, to switch other nodes on. |
| [Random LoRA](#random-lora) | Picks a random LoRA from a subfolder of the loras folder. |
| [Face Coverage](#face-coverage) | Outputs the percent of an image covered by detected faces. |

## Installation

Clone into `ComfyUI/custom_nodes` and install the requirements with ComfyUI's Python:

```
git clone https://github.com/tonyvo30/TonyVoComfyUINodes
pip install -r TonyVoComfyUINodes/requirements.txt
```

The only dependency is `opencv-python-headless`, used by Face Coverage. It is imported when the pack loads, so without it none of the nodes appear.

### Upgrading from Add Lora with String

The **Add Lora with String** node has been removed. It wrote `<lora:...>` strings for an external loader such as rgthree's Power Prompt. Workflows that use it show it as a missing node. Replace it with a [Keyword LoRA Rule](#keyword-lora-rule) chain and [Apply Keyword LoRAs](#apply-keyword-loras), which load the LoRAs directly:

| Add Lora with String | Keyword LoRA Rule |
| --- | --- |
| `lora` / `strength` | `lora_name` / `strength_model` and `strength_clip` |
| `lookup_string` | `match_any` |
| `and_string` | `require_all` |
| `not_string` | `exclude` |
| `custom_postitive_append` / `custom_negative_append` | `positive_append` / `negative_append`, or `trigger` for trigger words |
| `postitive_prompt` / `negative_prompt` | `positive` / `negative` on Apply Keyword LoRAs |

## Keyword LoRAs

Apply a LoRA only when its keywords appear in the prompt. Useful for LoRAs that teach one concept (a pose, an outfit, a style) but shift the whole model when loaded: they stay off until the prompt asks for them. Character LoRAs are selected the same way and passed to a dedicated image-only character loader.

### Keyword LoRA Rule
One rule per LoRA. Chain rules through `previous_rules` and connect the last one to **Apply Keyword LoRAs**.

| Input | Meaning |
| --- | --- |
| `lora_name` | LoRA to apply. `None` makes a rule that only edits the prompt text. |
| `strength_model` / `strength_clip` | LoRA strengths. A rule with both at 0 only edits the prompt text. |
| `match_any` | Comma separated. Matches when any of these appear. |
| `require_all` | Comma separated. Every one of these must also appear. |
| `exclude` | Comma separated. No match if any of these appear. |
| `positive_append` / `negative_append` | Comma separated words added to the prompts on a match. Words already present are skipped. |
| `trigger` | Comma separated trigger words. Added to the positive prompt before `positive_append` on a match, and passed out on the `trigger` output of Apply Keyword LoRAs. |

Matching is case-insensitive and whole-word (`cat` does not match `category`, but does match `black_cat`). Spaces in a keyword also match underscores or no space, so `chicken jockey` matches `chicken_jockey` and `chickenjockey`. Prompt weights such as `(chicken jockey:1.2)` still match.

Rules are evaluated in chain order and each rule sees the words added by the rules before it, so one rule can set off another. For example, a clothing rule appends its trigger word and a later texture rule matches on that trigger word.

### Keyword Character
Defines a character selected by keywords, with the same `match_any` / `require_all` / `exclude` logic as the rules. Only one character is selected per prompt: the first in the chain that matches. When selected, its words are appended to the prompts and its LoRA and strength are passed out of **Apply Keyword LoRAs** for a dedicated character loader, e.g. [Krea2T Character LoRA — Image Only](https://github.com/capitan01R/ComfyUI-Krea2T-Enhancer#character-lora--image-only), which applies the character LoRA to image tokens only. Apply Keyword LoRAs never loads the character's LoRA itself, so a rule or inline tag for it does not apply it a second time.

| Input | Meaning |
| --- | --- |
| `lora_name` | Character LoRA. Passed out of Apply Keyword LoRAs for the character loader. |
| `strength` | Character LoRA strength for the character loader. |
| `match_any` | Comma separated. The character is selected when any of these appear. |
| `require_all` | Comma separated. Every one of these must also appear. |
| `exclude` | Comma separated. Not selected if any of these appear. |
| `positive_append` / `negative_append` | Comma separated words appended to the prompts on a selection. |
| `trigger` | Comma separated trigger words. Added to the positive prompt before `positive_append` on a selection, and passed out on the `trigger` output of Apply Keyword LoRAs. |

Chain characters through `previous_characters`. Characters are checked before the rules, so a rule can match on a selected character's words: e.g. a character appends `janedoe` and a later rule matches on `janedoe`.

### Apply Keyword LoRAs
Applies inline tags and matched rules to the model and CLIP, selects the character, and outputs the final prompts.

| Input | Meaning |
| --- | --- |
| `model` / `clip` | Model and optional CLIP to patch. |
| `positive` | Positive prompt. May contain inline `<lora:...>` tags. |
| `negative` | Optional negative prompt. |
| `rules` | Optional chain of Keyword LoRA Rule nodes. |
| `characters` | Optional chain of Keyword Character nodes. |
| `character_override` | `auto` picks the character by keywords, `none` disables characters, and a LoRA name forces the character that uses it. A LoRA with no Keyword Character is selected at strength 1 with nothing appended. |

| Output | Meaning |
| --- | --- |
| `MODEL` / `CLIP` | Patched model and CLIP. |
| `positive` / `negative` | Final prompts, with inline tags removed and all appended words added. |
| `report` | What was applied, selected or skipped, and why. Also written to the log. |
| `character_lora` / `character_strength` / `character_enabled` | The selected character's LoRA, strength and on/off state for the character loader. With no character selected, the LoRA name is empty and `character_enabled` is false, so the loader stays bypassed. |
| `added_positive` / `added_negative` | Only the words the selected character and matched rules appended, in the order they were added. Trigger words, and words skipped because the prompt already had them, are not included. |
| `trigger` | Trigger words of the selected character and every matched rule, without duplicates, including ones the prompt already contained. |

To preview the prompts on the canvas, connect the text outputs to a text display node such as ShowText (was-node-suite) or PreviewAny (Impact Pack).

The positive prompt can contain inline tags, which are applied and removed from the text: `<lora:name>`, `<lora:name:strength>` or `<lora:name:model_strength:clip_strength>`. `name` can be the file name or the path inside the loras folder, with or without extension, using either slash direction. A tag whose name is ambiguous, not found, or has a non-numeric strength is skipped and listed in the report.

Each LoRA is applied at most once; the first inline tag or rule that applies it wins.

The LoRA files used by the last run stay in memory, so re-running with a different prompt does not reread them from disk. A file is reloaded when it changes on disk.

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
Outputs `matched` (true/false) and a `reason` using the same `match_any` / `require_all` / `exclude` logic as the rules. Connect `matched` to another node's `enabled` input to switch it on by keyword. Feed `text` from the `positive` output of Apply Keyword LoRAs so words added by rules count. Inline `<lora:...>` tags in the text are ignored. For character LoRAs, use Keyword Character instead: Apply Keyword LoRAs passes the selected character to the character loader directly.

### Random LoRA
Picks a random LoRA from a subfolder of the loras folder, e.g. `characters/test`. Only LoRAs directly inside the folder are picked, not ones in its subfolders. `seed` makes the pick repeatable; set it to randomize to get a new pick each run. Connect `lora_name` to `character_override` on Apply Keyword LoRAs to force a random character.

## Face Coverage
Detects faces with OpenCV YuNet and outputs `percent`, the share of the image covered by face boxes (overlapping boxes count once). For a batch it outputs the average. Boxes include a little hair and background around the face, so a tight close-up reads around 50%.

Place a YuNet model, e.g. `face_detection_yunet_2023mar.onnx` or `face_detection_yunet_2026may.onnx` from [opencv_zoo](https://github.com/opencv/opencv_zoo/tree/main/models/face_detection_yunet), in `models/yunet`. Only `.onnx` files are listed. `score_threshold` is the minimum detection confidence; lower finds more faces but more false ones.

Images are measured on a copy downscaled to 640 px on the long side, since YuNet misses large close-up faces at full resolution. An alpha channel is ignored.

## Tests
From the repo root:

```
python -m unittest discover tests
```
