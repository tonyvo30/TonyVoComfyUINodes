## Tony Vo ComfyUI Nodes
Personal nodes that I made since I wanted to consolidate a lot of logic to perform simple tasks.

# Add Lora With String
Dynamically add lora strings and additional keywords based keywords within prompt. This node is meant to be used with a loader like rgthree's power prompt to apply the lora strings, e.g. `<lora:model\loraName:strength>`. The node simply does string manipulations, so the nodes can be chained to apply multiple loras. 

The keywords in the AND field are required to apply the lora, while words in the NOT field must not exist to apply the lora string.

custom_positive_append and custom_negative_append are to append words into the respective prompt. Can be used to apply trigger words or apply negative words to prompt which can be useful for overtrained loras.
  
![image](https://github.com/user-attachments/assets/78ba826d-f323-4fef-a97d-ca15d07b5aef)

![image](https://github.com/user-attachments/assets/ac72418f-e80d-41f1-ac47-3fd0e131a657)
