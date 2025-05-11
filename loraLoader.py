import os
import folder_paths
from .loraLoaderUtils import containEntry, appendPrompt

class addLoraWithString:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "postitive_prompt": ("STRING", {"multiline": True, "default": ""}),
                "negative_prompt": ("STRING", {"multiline": True, "default": ""}),
                "lora": (['CHOOSE'] +
                        [os.path.splitext(x)[0] for x in folder_paths.get_filename_list('loras')],),
                "strength": ("FLOAT", {"default": 1.0, "min": -10.0, "max": 10.0, "step": 0.01}),
                "lookup_string": ("STRING", {"multiline": True, "default": ""}),
                "and_string": ("STRING", {"multiline": True, "default": ""}),
                "not_string": ("STRING", {"multiline": True, "default": ""}),
                "custom_postitive_append": ("STRING", {"multiline": True, "default": ""}),
                "custom_negative_append": ("STRING", {"multiline": True, "default": ""}),
            },
        }
    
    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("positive prompt", "negative prompt")
    FUNCTION = "addLoraToPrompt"
    CATEGORY = "TonyVoNodes"

    def addLoraToPrompt(self, postitive_prompt, negative_prompt, lora, strength, lookup_string, and_string, not_string, custom_postitive_append, custom_negative_append):
        if (lora == 'CHOOSE' or strength == 0 or lookup_string == '' or not containEntry(lookup_string, and_string, not_string, postitive_prompt)):
            return (postitive_prompt, negative_prompt) 
        
        appendedPositivePrompt = postitive_prompt
        appendedNegativePrompt = negative_prompt
        if (custom_postitive_append):
            appendedPositivePrompt = appendPrompt(appendedPositivePrompt, custom_postitive_append)
        if (custom_negative_append):
            appendedNegativePrompt = appendPrompt(appendedNegativePrompt, custom_negative_append)


        loraString = '<lora:' + lora + ':' + str(strength) + '>'
        newPositivePrompt = appendedPositivePrompt + ' ' + loraString + ' '
        return (newPositivePrompt, appendedNegativePrompt)
