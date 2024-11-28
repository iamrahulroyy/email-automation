from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
from dotenv import load_dotenv
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import time
import threading
from database import init_db, is_file_processed, mark_file_processed
from datetime import datetime
from tkinter import Tk, Label, Entry, Button, StringVar, messagebox
import tkinter as tk
import logging
import sys
import webbrowser
from tkinter import filedialog
from pathlib import Path

# Configure basic logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

# Load environment variables
try:
    load_dotenv()
except OSError:
    # Silently continue if .env file is not found
    pass

app = FastAPI()

class EmailRequest(BaseModel):
    subject: str
    recipient: str
    body: str

# Email configuration
EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587

# Obsidian configuration
# OBSIDIAN_VAULT_PATH = "C:/obsidian vault"  # Replace with your path
RECIPIENT_EMAIL = "rahulroy.agtt@gmail.com"  # Replace with your email

class StatusWindow:
    def __init__(self):
        # Load both OBSIDIAN_VAULT_PATH and EMAIL_ADDRESS at initialization
        self.obsidian_vault_path = os.getenv("OBSIDIAN_VAULT_PATH", "Not set")
        self.email_address = os.getenv("EMAIL_ADDRESS", "Not set")  # Add this line
        
        self.root = tk.Tk()
        self.root.title("Obsidian Email Service")
        # self.root.geometry("400x250")
        self.email_format_window = None
        window_width = 400
        window_height = 250
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()

        # Calculate position x, y to center the window
        position_x = int((screen_width / 2) - (window_width / 2))
        position_y = int((screen_height / 2) - (window_height / 2))
        self.root.geometry(f"{window_width}x{window_height}+{position_x}+{position_y}")


        try:
            self.root.iconbitmap('logo.ico') 
        except:
            pass  # If icon file not found, use default icon

        # Create main frame
        main_frame = tk.Frame(self.root, padx=20, pady=20)
        main_frame.pack(expand=True, fill='both')

        # Status label with larger font
        self.status_label = tk.Label(
            main_frame, 
            text="Service Status: Running", 
            font=('Arial', 12, 'bold'),
            fg='green'
        )
        self.status_label.pack(pady=10)

        # Add Email configuration info
        self.email_info = tk.Label(
            main_frame,
            text=f"Email: {self.email_address}",  # Use instance variable instead of direct ENV
            font=('Arial', 10)
        )
        self.email_info.pack(pady=5)

        # Add vault path info
        self.vault_info = tk.Label(
            main_frame,
            text=f"Watching: {self.obsidian_vault_path}",
            font=('Arial', 10),
            wraplength=300
        )
        self.vault_info.pack(pady=5)

        # Buttons frame
        button_frame = tk.Frame(main_frame)
        button_frame.pack(pady=20)

        # Modify the stop button to be more dynamic
        self.service_button = tk.Button(   
            button_frame,
            text="Stop Service",
            command=self.toggle_service,
            bg='#ff4444',
            fg='white',
            font=('Arial', 10, 'bold')
        )
        self.service_button.pack(side=tk.LEFT, padx=5)

        # Reset credentials button
        self.reset_button = tk.Button(
            button_frame,
            text="Reset Credentials",
            command=self.reset_credentials,
            font=('Arial', 10)
        )
        self.reset_button.pack(side=tk.LEFT, padx=5)

        # Help button for email format
        self.help_button = tk.Button(
            button_frame,
            text="Email Format",
            command=self.show_email_format,
            bg='#ff4444',
            fg='black',
            font=('Arial', 10)
        )
        self.help_button.pack(side=tk.LEFT, padx=5)


        # Protocol for closing window
        self.root.protocol("WM_DELETE_WINDOW", self.stop_service_and_close)
        
        # Flag to track if service is running
        self.is_running = True

    def stop_service_and_close(self):
        """
        Method to stop the service and close the window when the user clicks the 'X' button.
        """
        if self.is_running:
            self.stop_service()  # Stop the service properly
        self.root.destroy()  # Close the window    


    def toggle_service(self):
        if self.is_running:
            # Stop the service
            self.is_running = False
            self.status_label.config(text="Service Status: Stopped", fg='red')
            self.service_button.config(text="Start Service", bg='#44ff44')  # Change to green
            
            # Stop the existing threads here if needed
            # You might want to add logic to stop your observer and server
        else:
            # Start the service
            self.is_running = True
            self.status_label.config(text="Service Status: Running", fg='green')
            self.service_button.config(text="Stop Service", bg='#ff4444')  # Change to red
            
            # Restart the service threads
            self.restart_service_threads()

    def restart_service_threads(self):
        # Start the file watcher in a separate thread
        watcher_thread = threading.Thread(target=start_file_watcher, daemon=True)
        watcher_thread.start()
        
        # Start the FastAPI server in a separate thread
        def run_server():
            import uvicorn
            try:
                config = uvicorn.Config(
                    app,
                    host="localhost",
                    port=8002,
                    log_config=None,
                    access_log=False
                )
                server = uvicorn.Server(config)
                server.run()
            except OSError as e:
                if "only one usage of each socket address" in str(e):
                    logging.warning("Server already running on port 8002")
                else:
                    logging.error(f"Failed to start server: {e}")
        
        server_thread = threading.Thread(target=run_server, daemon=True)
        server_thread.start()

    # Replace the old stop_service method
    def stop_service(self):
        self.toggle_service()

    def reset_credentials(self):
        if messagebox.askyesno("Confirm", "Are you sure you want to reset credentials? The application will need to be restarted."):
            if os.path.exists(".env"):
                os.remove(".env")
                messagebox.showinfo("Success", "Credentials reset. Please restart the application.")
                self.root.quit()

    def show_email_format(self):
        # Create a new popup window
        if self.email_format_window is not None:
            self.email_format_window.lift()
            return
        
        self.email_format_window = tk.Toplevel(self.root)
        self.email_format_window.title("Email Format Help")
        self.email_format_window.geometry("400x250")

        self.email_format_window.protocol("WM_DELETE_WINDOW", self.close_email_format_window)
        
        # Text widget with the email format example
        help_text = """#sender: Name 
- Today's Task
- [ ] Task 1
- [ ] Task 2
-------------------
- Tomorrow's Task
- [ ] Task 1
- [ ] Task 2
#send"""
        
        label = tk.Label(self.email_format_window, text="Write your email in Obsidian using the following format:", font=('Arial', 10, 'bold'))
        label.pack(pady=10)

        text_widget = tk.Text(self.email_format_window, height=10, width=50)
        text_widget.insert(tk.END, help_text)
        text_widget.config(state=tk.DISABLED)  # Make the text read-only
        text_widget.pack(padx=10, pady=10)


    def close_email_format_window(self):
        if self.email_format_window is not None:
            self.email_format_window.destroy()  # Close the popup window
            self.email_format_window = None

    def minimize_to_tray(self):
        self.root.iconify()  # Minimize window instead of closing

    def run(self):
        self.root.mainloop()

def send_email(subject: str, recipient: str, body: str):
    try:
        logging.info(f"Attempting to send email to: {recipient}")
        if not EMAIL_ADDRESS or not EMAIL_PASSWORD:
            logging.error("Email credentials not properly loaded")
            logging.debug(f"EMAIL_ADDRESS: {'present' if EMAIL_ADDRESS else 'missing'}")
            logging.debug(f"EMAIL_PASSWORD: {'present' if EMAIL_PASSWORD else 'missing'}")
            raise ValueError("Email credentials not configured")

        # Create message
        message = MIMEMultipart()
        message["From"] = EMAIL_ADDRESS
        message["To"] = recipient
        message["Subject"] = subject
        message.attach(MIMEText(body, "plain"))

        # Enhanced error handling for SMTP connection
        try:
            with smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=30) as server:
                server.set_debuglevel(1)  # Enable debug output
                server.starttls()
                logging.info("Attempting login...")
                server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
                logging.info("Login successful, sending message...")
                server.send_message(message)
                logging.info("Email sent successfully")
        except smtplib.SMTPAuthenticationError:
            logging.error("Authentication failed. Please check your email and app password.")
            raise ValueError("Invalid email credentials. Make sure you're using an App Password for Gmail.")
        except smtplib.SMTPException as smtp_error:
            logging.error(f"SMTP error occurred: {smtp_error}")
            raise

        return True
    except Exception as e:
        logging.error(f"Failed to send email: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/send-email")
async def send_email_endpoint(email_request: EmailRequest):
    try:
        send_email(email_request.subject, email_request.recipient, email_request.body)
        return {"message": "Email sent successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class ObsidianHandler(FileSystemEventHandler):
    def __init__(self):
        self.last_modified = {}

    def parse_content(self, content):
        """
        Parse content to check format:
        #sender: Name 
        Today's Task
        .
        .
        -------------------
        Tomorrow's Task
        .
        .
        #send
        """
        lines = content.split("\n")
        sender_name = None
        tasks = []
        has_send_tag = False

        # First find sender
        for line in lines:
            if line.replace(" ", "").startswith("#sender:"):  # Remove all spaces before checking
                # Extract the part after "#sender:" regardless of spaces
                sender_part = line[line.find("#sender")+7:].strip()
                sender_name = sender_part
            # Check for #send tag anywhere in the content
            elif line.strip() == "#send":
                has_send_tag = True
        # Then collect tasks
        for line in lines:
            if not line.strip().startswith("#"):
                tasks.append(line.strip())

        return has_send_tag, sender_name, tasks

    def on_modified(self, event):
        try:
            if event.is_directory:
                return

            file_path = event.src_path
            logging.info(f"File modified: {file_path}")

            # Skip if we've already processed this file
            if is_file_processed(file_path):
                logging.info(f"File already processed: {file_path}")
                return

            current_time = time.time()
            if file_path in self.last_modified:
                if current_time - self.last_modified[file_path] < 1:
                    logging.info("Skipping due to debounce")
                    return

            self.last_modified[file_path] = current_time

            logging.info(f"Reading file content: {file_path}")
            with open(file_path, "r", encoding="utf-8") as file:
                content = file.read()
            
            has_send_tag, sender_name, tasks = self.parse_content(content)
            logging.info(f"Parsed content - has_send_tag: {has_send_tag}, sender_name: {sender_name}, tasks count: {len(tasks)}")

            # Check required elements
            if not has_send_tag:
                print(f"#send tag not found in file: {file_path}")
                return

            if not sender_name:
                print(f"No sender name found in file: {file_path}")
                return

            if not tasks:
                print(f"No tasks found in file: {file_path}")
                return

            try:
                # Format email body
                email_body = f"""{sender_name} - {datetime.now().strftime('%Y-%m-%d')}:

{chr(10).join('• ' + task for task in tasks)}





"""
                # Send email
                send_email(
                    f"{sender_name}- {datetime.now().strftime('%Y-%m-%d')}",
                    RECIPIENT_EMAIL,
                    email_body,
                )

                # time.sleep(1)

                # Mark this file as processed
                mark_file_processed(file_path)
                print(f"Tasks email sent successfully for {file_path}!")

                # Add success message to file
                self.append_status_to_file(file_path, "sent OK")
            except Exception as e:
                print(f"Failed to send email for {file_path}. Error: {str(e)}")
                
                # Add failure message to file
                self.append_status_to_file(file_path, "sent Failed")

        except Exception as e:
            print(f"Error processing file: {str(e)}")

    def append_status_to_file(self, file_path, status):
        try:
            current_time = datetime.now().strftime("%I:%M %p - %d/%m/%y")
            with open(file_path, "a", encoding="utf-8") as file:
                file.write(f"\nServer Sent Timestamp: {current_time} : {status}\n")
        except Exception as e:
            print(f"Failed to write status to file: {str(e)}")

def start_file_watcher():
    # Get the vault path from environment variables
    obsidian_vault_path = os.getenv("OBSIDIAN_VAULT_PATH")
    
    if not obsidian_vault_path:
        logging.error("OBSIDIAN_VAULT_PATH not found in environment variables")
        return
        
    if not os.path.exists(obsidian_vault_path):
        logging.error(f"Vault path not found: {obsidian_vault_path}")
        return

    event_handler = ObsidianHandler()
    observer = Observer()
    observer.schedule(event_handler, obsidian_vault_path, recursive=True)
    observer.start()
    logging.info(f"Started watching Obsidian vault at: {obsidian_vault_path}")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()

# Update the load_dotenv logic to handle exe environments
def get_base_path():
    if getattr(sys, 'frozen', False):
        # Running as compiled exe
        return os.path.dirname(sys.executable)
    else:
        # Running as script
        return os.path.dirname(os.path.abspath(__file__))

# Update load_dotenv to use absolute path
def load_env_file():
    try:
        base_path = get_base_path()
        env_path = os.path.join(base_path, '.env')
        load_dotenv(env_path)
        return True
    except Exception as e:
        logging.error(f"Error loading .env file: {e}")
        return False

# Update save_credentials function
def save_credentials():
    email = email_var.get()
    password = password_var.get()
    vault_path = vault_path_var.get()

    if not email or not password or not vault_path:
        messagebox.showerror("Error", "All fields are required!")
        return

    # Validate email format
    if not "@" in email or not "." in email:
        messagebox.showerror("Error", "Please enter a valid email address!")
        return

    # Validate Gmail specifically
    if not email.lower().endswith("@gmail.com"):
        messagebox.showerror("Error", "Only Gmail addresses are supported!")
        return

    try:
        # Create a data directory if it doesn't exist
        data_dir = os.path.join(get_base_path(), "data")
        Path(data_dir).mkdir(exist_ok=True)
        
        env_path = os.path.join(get_base_path(), ".env")
        
        # Test email credentials before saving
        try:
            with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
                server.starttls()
                server.login(email, password)
        except smtplib.SMTPAuthenticationError:
            messagebox.showerror(
                "Error", 
                "Authentication failed! Please make sure you're using an App Password, not your regular Gmail password.\n\n"
                "Click 'Help' to learn how to create an App Password."
            )
            return
        
        # If authentication successful, save credentials
        with open(env_path, "w") as f:
            f.write(f"EMAIL_ADDRESS={email}\n")
            f.write(f"EMAIL_PASSWORD={password}\n")
            f.write(f"OBSIDIAN_VAULT_PATH={vault_path}\n")
            f.write(f"DB_PATH={os.path.join(data_dir, 'obsidian_email.db')}\n")

        if init_db():
            messagebox.showinfo("Success", "Credentials verified and saved successfully!")
            root.destroy()
            load_env_file()
            start_service()
        else:
            messagebox.showerror("Error", "Failed to initialize database")
            
    except Exception as e:
        logging.error(f"Failed to save credentials: {e}")
        messagebox.showerror("Error", f"Failed to save credentials: {str(e)}")

def open_help():
    # Redirects the user to the Gmail app password guide
    webbrowser.open("https://knowledge.workspace.google.com/kb/how-to-create-app-passwords-000009237")



def start_service():
    # Load environment variables before initializing
    if not load_env_file():
        messagebox.showerror("Error", "Failed to load configuration. Please check credentials.")
        return

    # Verify required environment variables
    required_vars = ["EMAIL_ADDRESS", "EMAIL_PASSWORD", "OBSIDIAN_VAULT_PATH"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        messagebox.showerror("Error", f"Missing required configuration: {', '.join(missing_vars)}")
        return

    # Initialize remaining services
    init_db()
    
    # Start the file watcher in a separate thread
    watcher_thread = threading.Thread(target=start_file_watcher, daemon=True)
    watcher_thread.start()
    
    # Start the FastAPI server in a separate thread
    def run_server():
        import uvicorn
        config = uvicorn.Config(
            app,
            host="localhost",
            port=8002,
            log_config=None,
            access_log=False
        )
        server = uvicorn.Server(config)
        server.run()
    
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()
    
    # Create and show the status window
    status_window = StatusWindow()
    status_window.run()

def select_vault_path():
    selected_path = filedialog.askdirectory(title="Select Obsidian Vault Path")
    if selected_path: 
        vault_path_var.set(selected_path) 





if __name__ == "__main__":
    # Make root global so it can be accessed in save_credentials
    global root
    
    has_credentials = (
        os.path.exists('.env') and
        os.getenv("EMAIL_ADDRESS") and
        os.getenv("EMAIL_PASSWORD") and
        os.getenv("OBSIDIAN_VAULT_PATH")
    )

    if not has_credentials:
        root = Tk()
        root.title("Setup Credentials")

        # Set window size and position it in the center of the screen
        window_width = 300
        window_height = 150
        
        screen_width = root.winfo_screenwidth()
        screen_height = root.winfo_screenheight()

        # Calculate x and y coordinates for the window to be centered
        x = (screen_width // 2) - (window_width // 2)
        y = (screen_height // 2) - (window_height // 2)

        root.geometry(f"{window_width}x{window_height}+{x}+{y}")


        email_var = StringVar()
        password_var = StringVar()
        vault_path_var = StringVar()
        Label(root, text="Gmail Address:").grid(row=0, column=0)
        Entry(root, textvariable=email_var).grid(row=0, column=1)
        Label(root, text="Gmail App Password:").grid(row=1, column=0)
        Entry(root, textvariable=password_var, show='*').grid(row=1, column=1)

        Label(root, text="Obsidian Vault Path:").grid(row=2, column=0) 
        Entry(root, textvariable=vault_path_var).grid(row=2, column=1)  
        
        Button(root, text="Browse", command=select_vault_path).grid(row=2, column=2)


        Button(root, text="Save", command=save_credentials).grid(row=3, columnspan=2)
        Button(root, text="Help", command=open_help).grid(row=3, column=2, columnspan=2)

        root.mainloop()
    else:
        OBSIDIAN_VAULT_PATH = os.getenv("OBSIDIAN_VAULT_PATH")
        start_service()
