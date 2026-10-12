"""Keyword matching and prompt editing for keyword-triggered LoRAs.

Pure Python with no ComfyUI imports, so it can be unit tested on its own.
"""

import re
from dataclasses import dataclass

NO_LORA = "None"
CHARACTER_AUTO = "auto"
NO_CHARACTER = "none"
CHARACTER_IMAGE_ONLY = "image only"
CHARACTER_FULL_LORA = "full LoRA"

# <lora:name>, <lora:name:strength> or <lora:name:model_strength:clip_strength>
INLINE_LORA_TAG_PATTERN = re.compile(r"<lora:([^:<>]+)(?::([^:<>]*))?(?::([^:<>]*))?>", re.IGNORECASE)

# A term only matches when it is not glued to a letter or digit on either side.
# Underscores count as separators so "cat" matches "black_cat".
TERM_START_BOUNDARY = r"(?<![^\W_])"
TERM_END_BOUNDARY = r"(?![^\W_])"


@dataclass(frozen=True)
class KeywordLoraRule:
    lora_name: str
    strength_model: float
    strength_clip: float
    match_any: str = ""
    require_all: str = ""
    exclude: str = ""
    positive_append: str = ""
    negative_append: str = ""
    trigger: str = ""


@dataclass(frozen=True)
class KeywordCharacter:
    lora_name: str
    strength: float
    match_any: str = ""
    require_all: str = ""
    exclude: str = ""
    positive_append: str = ""
    negative_append: str = ""
    trigger: str = ""
    apply_as: str = CHARACTER_IMAGE_ONLY


@dataclass(frozen=True)
class LoraApplication:
    lora_name: str
    strength_model: float
    strength_clip: float
    source: str


@dataclass(frozen=True)
class KeywordLoraResult:
    positive: str
    negative: str
    added_positive: str
    added_negative: str
    trigger: str
    lora_applications: tuple[LoraApplication, ...]
    selected_character: KeywordCharacter | None
    report_lines: tuple[str, ...]


def split_terms(term_list_text):
    """Split a comma or newline separated list, dropping blank entries."""
    return [term.strip() for term in re.split(r"[,\n]", term_list_text) if term.strip()]


def term_to_regex_pattern(term):
    """Spaces and underscores in a term match any run of spaces/underscores, or none."""
    words = [re.escape(word) for word in re.split(r"[\s_]+", term) if word]
    return TERM_START_BOUNDARY + r"[\s_]*".join(words) + TERM_END_BOUNDARY


def contains_term(text, term):
    return re.search(term_to_regex_pattern(term), text, re.IGNORECASE) is not None


def find_first_contained_term(text, terms):
    return next((term for term in terms if contains_term(text, term)), None)


def find_first_missing_term(text, terms):
    return next((term for term in terms if not contains_term(text, term)), None)


def strip_inline_lora_tags(text):
    without_tags, tag_count = INLINE_LORA_TAG_PATTERN.subn("", text)
    if tag_count == 0:
        return text
    # Tidy the gaps left behind: doubled commas and runs of spaces.
    without_tags = re.sub(r"\s*,(\s*,)+", ",", without_tags)
    without_tags = re.sub(r"[ \t]{2,}", " ", without_tags)
    return without_tags.strip().strip(",").strip()


def find_new_terms(text, additions_text):
    """Return each comma separated addition that the text does not already contain."""
    new_terms = []
    for term in split_terms(additions_text):
        already_present = contains_term(text, term) or any(contains_term(existing, term) for existing in new_terms)
        if not already_present:
            new_terms.append(term)
    return new_terms


def append_terms(text, terms):
    if not terms:
        return text
    trimmed_text = text.rstrip().rstrip(",").rstrip()
    joined_terms = ", ".join(terms)
    return f"{trimmed_text}, {joined_terms}" if trimmed_text else joined_terms


def describe_rule_match(rule, text):
    """Return (matched, reason) for a rule against the given prompt text."""
    return describe_keyword_match(text, rule.match_any, rule.require_all, rule.exclude)


def describe_keyword_match(text, match_any, require_all, exclude):
    """Return (matched, reason) for the three keyword lists against the given text."""
    match_any_terms = split_terms(match_any)
    require_all_terms = split_terms(require_all)
    if not match_any_terms and not require_all_terms:
        return False, "no keywords set"

    matched_term = None
    if match_any_terms:
        matched_term = find_first_contained_term(text, match_any_terms)
        if matched_term is None:
            return False, "no keyword found"

    missing_term = find_first_missing_term(text, require_all_terms)
    if missing_term is not None:
        return False, f'missing required "{missing_term}"'

    excluded_term = find_first_contained_term(text, split_terms(exclude))
    if excluded_term is not None:
        return False, f'excluded by "{excluded_term}"'

    if matched_term is not None:
        return True, f'matched "{matched_term}"'
    return True, "all required keywords found"


def normalize_lora_path(lora_path):
    return lora_path.replace("\\", "/").lower()


def remove_extension(lora_path):
    return re.sub(r"\.[^./]+$", "", lora_path)


def lora_folder(lora_name):
    """Subfolder of a LoRA inside the loras folder with forward slashes, "" for the top level."""
    path = lora_name.replace("\\", "/")
    return path.rsplit("/", 1)[0] if "/" in path else ""


def list_lora_folders(available_lora_names):
    return sorted({lora_folder(lora_name) for lora_name in available_lora_names} - {""})


def list_loras_in_folder(available_lora_names, folder):
    """LoRAs directly inside the folder, not in its subfolders."""
    return sorted(lora_name for lora_name in available_lora_names if lora_folder(lora_name) == folder)


def resolve_lora_name(requested_name, available_lora_names):
    """Find the LoRA file a tag refers to. Accepts the subfolder path or just the
    file name, with or without extension, using either slash direction.
    Raises LookupError when nothing or more than one file matches."""
    normalized_requested_name = normalize_lora_path(requested_name.strip())
    requested_name_without_extension = remove_extension(normalized_requested_name)
    has_subfolder = "/" in normalized_requested_name

    matching_lora_names = []
    for available_name in available_lora_names:
        normalized_available_name = normalize_lora_path(available_name)
        if normalized_requested_name in (normalized_available_name, remove_extension(normalized_available_name)):
            return available_name
        if not has_subfolder:
            file_name = normalized_available_name.rsplit("/", 1)[-1]
            if requested_name_without_extension == remove_extension(file_name) or normalized_requested_name == file_name:
                matching_lora_names.append(available_name)

    if len(matching_lora_names) == 1:
        return matching_lora_names[0]
    if matching_lora_names:
        raise LookupError(f'"{requested_name}" is ambiguous: {", ".join(matching_lora_names)}')
    raise LookupError(f'"{requested_name}" not found in the loras folder')


def parse_strength(strength_text, default_strength):
    if strength_text is None or not strength_text.strip():
        return default_strength
    return float(strength_text)


def format_strength(strength):
    return f"{strength:g}"


def select_character(text, characters, character_override):
    """Return (character or None, report lines). The override is CHARACTER_AUTO,
    NO_CHARACTER or a LoRA file name; otherwise the first character whose
    keywords match the text is chosen."""
    if character_override == NO_CHARACTER:
        return None, ["skipped  characters  (override set to none)"]
    if character_override != CHARACTER_AUTO:
        character = next((character for character in characters if character.lora_name == character_override), None)
        if character is None:
            character = KeywordCharacter(character_override, 1.0, apply_as=CHARACTER_FULL_LORA)
            return character, [f"character  {character_override}  strength 1  (override; no Character node uses this LoRA, applied as a full LoRA, nothing appended)"]
        return character, [f"character  {character.lora_name}  strength {format_strength(character.strength)}  (override)"]

    selected_character = None
    report_lines = []
    for character in characters:
        if selected_character is not None:
            report_lines.append(f"skipped  {character.lora_name}  (character {selected_character.lora_name} already selected)")
            continue
        matched, reason = describe_keyword_match(text, character.match_any, character.require_all, character.exclude)
        if matched:
            selected_character = character
            report_lines.append(f"character  {character.lora_name}  strength {format_strength(character.strength)}  ({reason})")
        else:
            report_lines.append(f"skipped  {character.lora_name}  ({reason})")
    return selected_character, report_lines


def evaluate_keyword_loras(positive, negative, rules, available_lora_names, characters=(), character_override=CHARACTER_AUTO):
    """Work out which LoRAs to apply and build the final prompts.

    Inline <lora:...> tags are parsed from the positive prompt. Then one
    character is selected and its text appended, so rules can react to it.
    Tags and rules are then applied in chain order, and each rule sees the
    words appended before it, so one rule's trigger words can set off a later
    rule. A LoRA is applied at most once: the first tag or rule that applies
    it wins, and the selected character's LoRA takes precedence over both.
    A full LoRA character is applied here; an image only character is not,
    and is returned for a dedicated character loader.
    """
    lora_applications = []
    report_lines = []
    applied_lora_names = set()
    added_positive_terms = []
    added_negative_terms = []
    trigger_terms = []

    def append_to_prompts(trigger, positive_append, negative_append):
        nonlocal positive, negative
        trigger_terms.extend(find_new_terms(", ".join(trigger_terms), trigger))
        positive = append_terms(positive, find_new_terms(positive, trigger))
        new_positive_terms = find_new_terms(positive, positive_append)
        new_negative_terms = find_new_terms(negative, negative_append)
        positive = append_terms(positive, new_positive_terms)
        negative = append_terms(negative, new_negative_terms)
        added_positive_terms.extend(new_positive_terms)
        added_negative_terms.extend(new_negative_terms)

    def add_lora_application(lora_application):
        if lora_application.lora_name in applied_lora_names:
            report_lines.append(f"skipped  {lora_application.lora_name}  ({lora_application.source}; already applied)")
            return
        applied_lora_names.add(lora_application.lora_name)
        lora_applications.append(lora_application)
        report_lines.append(
            f"applied  {lora_application.lora_name}  model {format_strength(lora_application.strength_model)}"
            f" clip {format_strength(lora_application.strength_clip)}  ({lora_application.source})"
        )

    tag_applications = []
    for tag_match in INLINE_LORA_TAG_PATTERN.finditer(positive):
        tag_text = tag_match.group(0)
        try:
            lora_name = resolve_lora_name(tag_match.group(1), available_lora_names)
            strength_model = parse_strength(tag_match.group(2), 1.0)
            strength_clip = parse_strength(tag_match.group(3), strength_model)
        except LookupError as error:
            report_lines.append(f"error    {tag_text}  ({error})")
            continue
        except ValueError:
            report_lines.append(f"error    {tag_text}  (strength is not a number)")
            continue
        tag_applications.append(LoraApplication(lora_name, strength_model, strength_clip, f"inline tag {tag_text}"))

    positive = strip_inline_lora_tags(positive)

    selected_character, character_report_lines = select_character(positive, characters, character_override)
    report_lines.extend(character_report_lines)
    if selected_character is not None:
        append_to_prompts(selected_character.trigger, selected_character.positive_append, selected_character.negative_append)
        if selected_character.apply_as == CHARACTER_FULL_LORA:
            add_lora_application(LoraApplication(selected_character.lora_name, selected_character.strength,
                                                 selected_character.strength, "character, full LoRA"))
        else:
            applied_lora_names.add(selected_character.lora_name)

    for tag_application in tag_applications:
        add_lora_application(tag_application)

    for rule in rules:
        rule_label = rule.lora_name if rule.lora_name != NO_LORA else "(text-only rule)"
        matched, reason = describe_rule_match(rule, positive)
        if not matched:
            report_lines.append(f"skipped  {rule_label}  ({reason})")
            continue

        append_to_prompts(rule.trigger, rule.positive_append, rule.negative_append)

        lora_has_effect = rule.strength_model != 0 or rule.strength_clip != 0
        if rule.lora_name != NO_LORA and lora_has_effect:
            add_lora_application(LoraApplication(rule.lora_name, rule.strength_model, rule.strength_clip, f"rule {reason}"))
        else:
            report_lines.append(f"matched  {rule_label}  ({reason}; text only, no LoRA applied)")

    return KeywordLoraResult(positive, negative, ", ".join(added_positive_terms), ", ".join(added_negative_terms),
                             ", ".join(trigger_terms),
                             tuple(lora_applications), selected_character, tuple(report_lines))
