import tkinter as tk
from tkinter import messagebox, filedialog, scrolledtext
from PIL import Image, ImageTk
import requests
import io
import random
import json
import threading
import re
import win32clipboard

class ChatImageApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Chat and Image Generator")

        # Adjust GUI size
        self.root.geometry("560x900")

        self.image = None  # To store the generated image
        self.conversation_history = []  # To maintain conversation context

        # Create the layout
        self.create_widgets()

        # Add the PGPT-BASIC.png image at the start
        self.display_placeholder_image()

    def create_widgets(self):
        # Main Frame
        main_frame = tk.Frame(self.root)
        main_frame.pack(fill="both", expand=True)

        # Image Display at the top (reserve space from the start)
        self.image_label = tk.Label(main_frame)
        self.image_label.pack(pady=10)
        self.image_label.bind("<Button-3>", self.copy_image_to_clipboard)  # Right-click to copy image

        # Chat Display (Canvas) below the image
        self.chat_display = scrolledtext.ScrolledText(main_frame, state='disabled', width=64, height=12, wrap='word')
        self.chat_display.pack(pady=10)

        # Input Frame under the chat
        self.entry_frame = tk.Frame(main_frame)
        self.entry_frame.pack(pady=5, fill='x')

        # Save Button (Left side of input area, small size)
        self.save_button = tk.Button(self.entry_frame, text="Save", command=self.save_image, state=tk.DISABLED)
        self.save_button.pack(side='left', padx=5, ipadx=5, ipady=5)

        # Prompt Entry (Input Area)
        self.prompt_text = tk.Text(self.entry_frame, height=4, width=48, wrap='word')
        self.prompt_text.pack(side='left', padx=5, fill='x', expand=True)
        self.prompt_text.bind("<Return>", self.send_message)
        self.prompt_text.bind("<Shift-Return>", self.newline_in_entry)

        # Scrollbar for Prompt Entry
        self.entry_scrollbar = tk.Scrollbar(self.entry_frame, command=self.prompt_text.yview)
        self.entry_scrollbar.pack(side='right', fill='y')
        self.prompt_text['yscrollcommand'] = self.entry_scrollbar.set

    def display_placeholder_image(self):
        """
        Display the custom PGPT-BASIC.png image at startup.
        """
        try:
            image = Image.open("PGPT-BASIC.png")  # Load your custom PNG file
            max_size = (540, 540)  # Resize it to fit the display area
            image.thumbnail(max_size, Image.LANCZOS)

            # Convert the image to PhotoImage and display it
            self.photo_image = ImageTk.PhotoImage(image)
            self.image_label.config(image=self.photo_image)
            self.image = image  # Store the image

        except Exception as e:
            print(f"Error loading image: {e}")
            # If there's an issue, fall back to the grey placeholder image
            placeholder_image = Image.new('RGB', (540, 540), color='lightgrey')
            self.photo_image = ImageTk.PhotoImage(placeholder_image)
            self.image_label.config(image=self.photo_image)

    def newline_in_entry(self, event):
        self.prompt_text.insert(tk.INSERT, "\n")
        return 'break'

    def update_chat(self, sender, message):
        """
        Updates the chat display with the sender and message.
        """
        clean_message = self.clean_message(message)
        self.chat_display.config(state='normal')
        self.chat_display.insert(tk.END, f"{sender}: {clean_message}\n\n")
        self.chat_display.config(state='disabled')
        self.chat_display.see(tk.END)

    def clean_message(self, message):
        """
        Clean up the message by removing markdown for images and normalizing line breaks.
        """
        # Remove image markdown using regex
        message = re.sub(r'!\[IMAGE\]\(.*?\)', '', message)
        # Normalize to single \n between paragraphs
        message = re.sub(r'\n+', '\n', message.strip())
        return message

    def get_ai_response(self):
        """
        Requests AI response and updates the conversation.
        """
        api_url = "https://text.pollinations.ai"
        headers = {'Content-Type': 'application/json'}

        data = {
            "messages": self.conversation_history  # Using the updated conversation history
        }

        try:
            response = requests.post(api_url, headers=headers, data=json.dumps(data), timeout=30)
            response.raise_for_status()
            ai_response = response.text.strip()
            print(f"AI Response Received: {ai_response}")  # Debugging

            # Add AI's response to the conversation history
            self.conversation_history.append({"role": "assistant", "content": ai_response})

            # Process and display the AI's response in the chat window
            self.update_chat("AI", ai_response)

            # Check if AI's response contains an image prompt
            image_prompt = self.extract_image_prompt(ai_response)
            if image_prompt:
                # Start image generation
                threading.Thread(target=self.generate_image, args=(image_prompt,)).start()

        except requests.exceptions.RequestException as e:
            print(f"Request error: {e}")
            self.update_chat("System", "Sorry, I couldn't process your message.")

    def send_message(self, event=None):
        user_message = self.prompt_text.get("1.0", tk.END).strip()
        if not user_message:
            messagebox.showwarning("Input Required", "Please enter a message.")
            return 'break'

        # Add user's message to conversation history
        self.conversation_history.append({"role": "user", "content": user_message})
        print(f"Conversation History (User Input Added): {self.conversation_history}")  # Debugging

        # Trim the history to maintain 5 user and 5 AI messages (10 total)
        self.trim_conversation_history()

        # Prepend the persona/context to the oldest user message before sending to AI
        self.prepend_persona_to_oldest()

        # Display the user message in the chat
        self.update_chat("You", user_message)

        # Clear the input box after sending the message
        self.prompt_text.delete("1.0", tk.END)

        # Send AI response in a separate thread to avoid freezing UI
        threading.Thread(target=self.get_ai_response).start()

        return 'break'  # Prevent default newline behavior

    def trim_conversation_history(self):
        """
        Trim the conversation history to 5 user + 5 AI messages.
        """
        max_messages = 5
        total_messages = len(self.conversation_history)
        
        # If the total number of messages exceeds 10, trim it
        if total_messages > max_messages * 2:  # 5 user + 5 AI = 10 messages total
            # Trim oldest messages to maintain 5 user + 5 AI
            self.conversation_history = self.conversation_history[-(max_messages * 2):]
            print(f"Trimmed conversation history: {self.conversation_history}")  # Debugging

    def prepend_persona_to_oldest(self):
        """
        Prepend the persona/context message to the oldest user message in the conversation history.
        """
        # Persona message to prepend to the oldest user message
        context_message = (
            "CONTEXT: Responding from perspective of current narrative always generate images for chat responses using the format ![IMAGE](Descriptive_Prompt, Desired_Style). When others direct image prompting, use keywords like 'create' for standalone images, 'add' for new elements to existing images, and 'mix' for combining all previous elements in one scene. "
            "You always chat and show images at the same time unless asked not to, so do not ask for permission to generate an image."
        )

        # Find the oldest user message in conversation history and prepend the context
        for i, message in enumerate(self.conversation_history):
            if message['role'] == 'user':
                self.conversation_history[i]['content'] = context_message + " " + self.conversation_history[i]['content']
                print(f"Prepended context to oldest user message: {self.conversation_history[i]['content']}")  # Debugging
                break  # Only prepend to the oldest user message, so stop after the first one.

    def extract_image_prompt(self, text):
        """
        Extracts image description from the markdown IMAGE syntax in the AI's response.
        """
        pattern = r'!\[IMAGE\]\(.*?\)'  # Capture the markdown format for images
        match = re.search(pattern, text)
        if match:
            return match.group(0)  # Return the entire image description for generating the image
        return None

    def request_ai_response(self):
        """
        Sends the conversation history to the AI and returns the AI's response.
        """
        api_url = "https://text.pollinations.ai"
        headers = {'Content-Type': 'application/json'}

        # Only send the last 5 user and 5 AI messages for context
        history_block = self.conversation_history[-10:]  # Adjust as needed to limit history block size

        data = {
            "messages": history_block
        }

        try:
            print(f"Sending request to AI with data: {json.dumps(data, indent=2)}")  # Debugging request payload
            response = requests.post(api_url, headers=headers, data=json.dumps(data), timeout=30)
            response.raise_for_status()
            ai_response = response.text.strip()
            # Add AI response to conversation history
            self.conversation_history.append({"role": "assistant", "content": ai_response})
            print(f"AI Response Received: {ai_response}")  # Debugging AI's full response
            return ai_response
        except requests.exceptions.RequestException as e:
            print(f"Request error: {e}")
            return None

    def generate_image(self, prompt):
        print(f"Generating image for prompt: {prompt}")  # Debugging image generation step

        # Disable the input and send button during image generation
        self.prompt_text.config(state='disabled')

        # Use the prompt to generate the image
        image = self.request_image(prompt)
        if image:
            self.display_image(image)
            self.save_button.config(state=tk.NORMAL)
            print("Image generated successfully.")  # Debugging successful image generation
        else:
            print("Failed to generate image.")  # Debugging image generation failure

        # Re-enable the input field
        self.prompt_text.config(state='normal')

    def request_image(self, prompt):
        """
        Requests the image from the image generation API using the prompt.
        """
        api_url = "https://image.pollinations.ai/prompt"
        seed = random.randint(1000, 9999)
        width, height = 1024, 1024  # Keep requested image quality

        # Encode the prompt for the URL
        encoded_prompt = requests.utils.quote(prompt)

        # Construct the full URL
        full_url = f"{api_url}/{encoded_prompt}?seed={seed}&width={width}&height={height}&nologo=true"

        print(f"Requesting image from URL: {full_url}")  # Debugging the image request URL
        try:
            response = requests.get(full_url, timeout=120)
            response.raise_for_status()

            # Load the image from the response content
            try:
                image = Image.open(io.BytesIO(response.content))
                print(f"Image received, size: {image.size}")  # Debugging received image info
                return image
            except Exception as e:
                print(f"Failed to load image from content, exception: {e}")
                print(f"Raw response content: {response.content[:500]}")  # Show first 500 bytes of content
                return None

        except requests.exceptions.RequestException as e:
            print(f"Request error: {e}")
            return None

    def display_image(self, image):
        """
        Displays the image in the GUI.
        """
        max_size = (540, 540)  # Adjust image size for display, but keep requested quality
        image.thumbnail(max_size, Image.LANCZOS)

        # Convert the image to PhotoImage
        self.photo_image = ImageTk.PhotoImage(image)
        self.image_label.config(image=self.photo_image)
        self.image = image  # Store the image

    def copy_image_to_clipboard(self, event):
        """
        Copy the generated image to the clipboard.
        """
        if self.image:
            output = io.BytesIO()
            self.image.convert('RGB').save(output, 'BMP')
            data = output.getvalue()[14:]  # BMP header is 14 bytes, remove it
            output.close()

            win32clipboard.OpenClipboard()
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardData(win32clipboard.CF_DIB, data)
            win32clipboard.CloseClipboard()

            messagebox.showinfo("Copied", "Image copied to clipboard!")
        else:
            messagebox.showwarning("No Image", "No image available to copy.")

    def save_image(self):
        """
        Saves the generated image to a file.
        """
        if self.image:
            file_path = filedialog.asksaveasfilename(defaultextension=".png",
                                                     filetypes=[("PNG Files", "*.png"), ("JPEG Files", "*.jpg"), ("All Files", "*.*")])
            if file_path:
                try:
                    self.image.save(file_path)
                    messagebox.showinfo("Image Saved", f"Image saved to {file_path}")
                except IOError:
                    messagebox.showerror("Save Error", "Failed to save image.")
        else:
            messagebox.showwarning("No Image", "No image to save.")

if __name__ == "__main__":
    root = tk.Tk()
    app = ChatImageApp(root)
    root.mainloop()
