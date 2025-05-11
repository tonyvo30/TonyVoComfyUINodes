import os
import re
import folder_paths

def containEntry(lookup_string, and_string, not_string, original_prompt):
        strippedPrompt = stripLoras(original_prompt)
        baseCondition = isAMatch(strippedPrompt, lookup_string)
        andCondition = isAMatch(strippedPrompt, and_string) if and_string else True
        notCondition = not isAMatch(strippedPrompt, not_string) if not_string else True
        return baseCondition and andCondition and notCondition

def stripLoras(prompt):
    pattern = r'<lora:([^:>]*?)(?::(-?\d*(?:\.\d*)?))?>'
    loraPaths = folder_paths.get_filename_list('loras')
    strippedLoraNames = {os.path.splitext(path)[0] for path in loraPaths}

    def replacement(match):
        loraName = match.group(1)
        if loraName in strippedLoraNames:
            return ''
        return match.group(0)

    return re.sub(pattern, replacement, prompt)

def isAMatch(prompt, lookupString):
    lookupVals = [val.strip() for val in lookupString.split(',')]
    pattern = r'(?<!\w)(?:' + '|'.join(re.escape(val).replace(r'\ ', r'[\s_]?') for val in lookupVals) + r')(?!\w)'
    return bool(re.search(pattern, prompt))
    
def appendPrompt(prompt, custom_append):
    strippedPrompt = stripLoras(prompt)
    promptWords = set(word.strip() for word in strippedPrompt.split(","))
    toAppendWords = set(word.strip() for word in custom_append.split(","))
    unique_words = toAppendWords - promptWords
    if unique_words:
        prompt += ", " + ", ".join(unique_words)
    return prompt