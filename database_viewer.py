"""
Simple GUI Database Viewer for Clinical Documentation AI
This provides a visual interface to view database contents
"""

import tkinter as tk
from tkinter import ttk, messagebox
import json
import mysql.connector
from mysql.connector import Error

class DatabaseViewer:
    """Simple GUI for viewing database contents"""
    
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Clinical Documentation AI - Database Viewer")
        self.root.geometry("1000x700")
        
        self.config = self.load_config()
        self.connection = None
        
        self.create_ui()
        
    def load_config(self):
        """Load database configuration"""
        try:
            with open('db_config.json', 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            return {
                "host": "localhost",
                "port": 3306,
                "user": "clinical_user",
                "password": "clinical_password", 
                "database": "clinical_docs"
            }
    
    def get_connection(self):
        """Get database connection"""
        try:
            if not self.connection or not self.connection.is_connected():
                self.connection = mysql.connector.connect(
                    host=self.config['host'],
                    port=self.config['port'],
                    user=self.config['user'],
                    password=self.config['password'],
                    database=self.config['database']
                )
            return self.connection
        except Error as e:
            messagebox.showerror("Database Error", f"Connection failed: {e}")
            return None
    
    def create_ui(self):
        """Create the user interface"""
        # Main frame
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Configure grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(1, weight=1)
        
        # Title
        title_label = ttk.Label(main_frame, text="Clinical Documentation AI - Database Viewer", 
                               font=('Arial', 16, 'bold'))
        title_label.grid(row=0, column=0, columnspan=2, pady=(0, 20))
        
        # Buttons frame
        buttons_frame = ttk.Frame(main_frame)
        buttons_frame.grid(row=1, column=0, sticky=(tk.W, tk.N), padx=(0, 20))
        
        # Buttons
        ttk.Button(buttons_frame, text="View Users", command=self.view_users).pack(fill=tk.X, pady=2)
        ttk.Button(buttons_frame, text="View Transcriptions", command=self.view_transcriptions).pack(fill=tk.X, pady=2)
        ttk.Button(buttons_frame, text="View SOAP Notes", command=self.view_soap_notes).pack(fill=tk.X, pady=2)
        ttk.Button(buttons_frame, text="View Settings", command=self.view_settings).pack(fill=tk.X, pady=2)
        ttk.Button(buttons_frame, text="Database Stats", command=self.view_stats).pack(fill=tk.X, pady=2)
        ttk.Button(buttons_frame, text="Test Connection", command=self.test_connection).pack(fill=tk.X, pady=2)
        ttk.Button(buttons_frame, text="Refresh", command=self.refresh_current_view).pack(fill=tk.X, pady=2)
        
        # Results frame
        results_frame = ttk.Frame(main_frame)
        results_frame.grid(row=1, column=1, sticky=(tk.W, tk.E, tk.N, tk.S))
        results_frame.columnconfigure(0, weight=1)
        results_frame.rowconfigure(0, weight=1)
        
        # Treeview for data display
        self.tree = ttk.Treeview(results_frame)
        self.tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Scrollbars
        v_scrollbar = ttk.Scrollbar(results_frame, orient=tk.VERTICAL, command=self.tree.yview)
        v_scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        self.tree.configure(yscrollcommand=v_scrollbar.set)
        
        h_scrollbar = ttk.Scrollbar(results_frame, orient=tk.HORIZONTAL, command=self.tree.xview)
        h_scrollbar.grid(row=1, column=0, sticky=(tk.W, tk.E))
        self.tree.configure(xscrollcommand=h_scrollbar.set)
        
        # Details text area
        details_frame = ttk.LabelFrame(main_frame, text="Details", padding="5")
        details_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(20, 0))
        details_frame.columnconfigure(0, weight=1)
        details_frame.rowconfigure(0, weight=1)
        
        self.details_text = tk.Text(details_frame, height=8, wrap=tk.WORD)
        self.details_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        details_scrollbar = ttk.Scrollbar(details_frame, orient=tk.VERTICAL, command=self.details_text.yview)
        details_scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        self.details_text.configure(yscrollcommand=details_scrollbar.set)
        
        # Bind tree selection
        self.tree.bind('<<TreeviewSelect>>', self.on_tree_select)
        
        # Current view tracker
        self.current_view = None
        self.current_data = []
        
        # Initial connection test
        self.test_connection()
    
    def clear_tree(self):
        """Clear the treeview"""
        for item in self.tree.get_children():
            self.tree.delete(item)
    
    def setup_tree_columns(self, columns):
        """Setup treeview columns"""
        self.tree["columns"] = columns
        self.tree["show"] = "headings"
        
        for col in columns:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=100, minwidth=50)
    
    def test_connection(self):
        """Test database connection"""
        connection = self.get_connection()
        if connection:
            self.details_text.delete(1.0, tk.END)
            self.details_text.insert(tk.END, "✅ Database connection successful!\n")
            self.details_text.insert(tk.END, f"Connected to: {self.config['database']} on {self.config['host']}\n")
            
            cursor = connection.cursor()
            cursor.execute("SELECT VERSION()")
            version = cursor.fetchone()[0]
            self.details_text.insert(tk.END, f"MySQL version: {version}\n")
            cursor.close()
        else:
            self.details_text.delete(1.0, tk.END)
            self.details_text.insert(tk.END, "❌ Database connection failed!\n")
            self.details_text.insert(tk.END, "Please check your database configuration.\n")
    
    def view_users(self):
        """View users table"""
        self.current_view = "users"
        connection = self.get_connection()
        if not connection:
            return
        
        cursor = connection.cursor()
        try:
            cursor.execute("SELECT id, username, created_at, is_active FROM users ORDER BY created_at DESC")
            users = cursor.fetchall()
            
            self.clear_tree()
            self.setup_tree_columns(["ID", "Username", "Created", "Active"])
            
            self.current_data = []
            for user in users:
                status = "Yes" if user[3] else "No"
                item_id = self.tree.insert("", tk.END, values=(user[0], user[1], user[2], status))
                self.current_data.append({"id": item_id, "data": user})
            
            self.details_text.delete(1.0, tk.END)
            self.details_text.insert(tk.END, f"Found {len(users)} users in database\n")
            
        except Error as e:
            messagebox.showerror("Database Error", f"Error viewing users: {e}")
        finally:
            cursor.close()
    
    def view_transcriptions(self):
        """View transcriptions table"""
        self.current_view = "transcriptions"
        connection = self.get_connection()
        if not connection:
            return
        
        cursor = connection.cursor()
        try:
            cursor.execute("""
                SELECT t.id, t.filename, u.username, t.language, t.status, t.created_at,
                       LEFT(t.transcription_text, 100) as text_preview
                FROM transcriptions t
                JOIN users u ON t.user_id = u.id
                ORDER BY t.created_at DESC
                LIMIT 50
            """)
            transcriptions = cursor.fetchall()
            
            self.clear_tree()
            self.setup_tree_columns(["ID", "Filename", "User", "Language", "Status", "Created"])
            
            self.current_data = []
            for trans in transcriptions:
                item_id = self.tree.insert("", tk.END, values=trans[:6])
                self.current_data.append({"id": item_id, "data": trans})
            
            self.details_text.delete(1.0, tk.END)
            self.details_text.insert(tk.END, f"Found {len(transcriptions)} transcriptions\n")
            self.details_text.insert(tk.END, "Select a row to view full transcription text\n")
            
        except Error as e:
            messagebox.showerror("Database Error", f"Error viewing transcriptions: {e}")
        finally:
            cursor.close()
    
    def view_soap_notes(self):
        """View SOAP notes"""
        self.current_view = "soap_notes"
        connection = self.get_connection()
        if not connection:
            return
        
        cursor = connection.cursor()
        try:
            cursor.execute("""
                SELECT t.id, t.filename, u.username, t.created_at, t.soap_note
                FROM transcriptions t
                JOIN users u ON t.user_id = u.id
                WHERE t.soap_note IS NOT NULL AND t.soap_note != '{}'
                ORDER BY t.created_at DESC
                LIMIT 20
            """)
            soap_notes = cursor.fetchall()
            
            self.clear_tree()
            self.setup_tree_columns(["ID", "Filename", "User", "Created"])
            
            self.current_data = []
            for note in soap_notes:
                item_id = self.tree.insert("", tk.END, values=note[:4])
                self.current_data.append({"id": item_id, "data": note})
            
            self.details_text.delete(1.0, tk.END)
            self.details_text.insert(tk.END, f"Found {len(soap_notes)} SOAP notes\n")
            self.details_text.insert(tk.END, "Select a row to view SOAP note details\n")
            
        except Error as e:
            messagebox.showerror("Database Error", f"Error viewing SOAP notes: {e}")
        finally:
            cursor.close()
    
    def view_settings(self):
        """View app settings"""
        self.current_view = "settings"
        connection = self.get_connection()
        if not connection:
            return
        
        cursor = connection.cursor()
        try:
            cursor.execute("SELECT setting_key, setting_value, updated_at FROM app_settings")
            settings = cursor.fetchall()
            
            self.clear_tree()
            self.setup_tree_columns(["Key", "Value", "Updated"])
            
            self.current_data = []
            for setting in settings:
                item_id = self.tree.insert("", tk.END, values=setting)
                self.current_data.append({"id": item_id, "data": setting})
            
            self.details_text.delete(1.0, tk.END)
            self.details_text.insert(tk.END, f"Found {len(settings)} app settings\n")
            
        except Error as e:
            messagebox.showerror("Database Error", f"Error viewing settings: {e}")
        finally:
            cursor.close()
    
    def view_stats(self):
        """View database statistics"""
        connection = self.get_connection()
        if not connection:
            return
        
        cursor = connection.cursor()
        try:
            # Get counts
            stats = {}
            
            cursor.execute("SELECT COUNT(*) FROM users")
            stats['Total Users'] = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM users WHERE is_active = TRUE")
            stats['Active Users'] = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM transcriptions")
            stats['Total Transcriptions'] = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM transcriptions WHERE soap_note IS NOT NULL AND soap_note != '{}'")
            stats['SOAP Notes'] = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM app_settings")
            stats['App Settings'] = cursor.fetchone()[0]
            
            # Database size
            cursor.execute("""
                SELECT ROUND(SUM(data_length + index_length) / 1024 / 1024, 2) AS 'Size'
                FROM information_schema.tables 
                WHERE table_schema = %s
            """, (self.config['database'],))
            size_result = cursor.fetchone()
            stats['Database Size (MB)'] = size_result[0] if size_result[0] else 0
            
            self.clear_tree()
            self.setup_tree_columns(["Statistic", "Value"])
            
            for key, value in stats.items():
                self.tree.insert("", tk.END, values=(key, value))
            
            self.details_text.delete(1.0, tk.END)
            self.details_text.insert(tk.END, "Database Statistics Summary\n")
            self.details_text.insert(tk.END, "=" * 30 + "\n")
            for key, value in stats.items():
                self.details_text.insert(tk.END, f"{key}: {value}\n")
            
        except Error as e:
            messagebox.showerror("Database Error", f"Error getting statistics: {e}")
        finally:
            cursor.close()
    
    def on_tree_select(self, event):
        """Handle tree selection"""
        selection = self.tree.selection()
        if not selection:
            return
        
        # Find the selected data
        selected_item_id = selection[0]
        selected_data = None
        
        for item in self.current_data:
            if item["id"] == selected_item_id:
                selected_data = item["data"]
                break
        
        if not selected_data:
            return
        
        # Display details based on current view
        self.details_text.delete(1.0, tk.END)
        
        if self.current_view == "users":
            self.details_text.insert(tk.END, f"User Details:\n")
            self.details_text.insert(tk.END, f"ID: {selected_data[0]}\n")
            self.details_text.insert(tk.END, f"Username: {selected_data[1]}\n")
            self.details_text.insert(tk.END, f"Created: {selected_data[2]}\n")
            self.details_text.insert(tk.END, f"Active: {selected_data[3]}\n")
            
        elif self.current_view == "transcriptions":
            self.details_text.insert(tk.END, f"Transcription Details:\n")
            self.details_text.insert(tk.END, f"ID: {selected_data[0]}\n")
            self.details_text.insert(tk.END, f"Filename: {selected_data[1]}\n")
            self.details_text.insert(tk.END, f"User: {selected_data[2]}\n")
            self.details_text.insert(tk.END, f"Language: {selected_data[3]}\n")
            self.details_text.insert(tk.END, f"Status: {selected_data[4]}\n")
            self.details_text.insert(tk.END, f"Created: {selected_data[5]}\n")
            self.details_text.insert(tk.END, f"\nTranscription Text:\n")
            self.details_text.insert(tk.END, f"{selected_data[6]}\n")
            
        elif self.current_view == "soap_notes":
            self.details_text.insert(tk.END, f"SOAP Note Details:\n")
            self.details_text.insert(tk.END, f"ID: {selected_data[0]}\n")
            self.details_text.insert(tk.END, f"Filename: {selected_data[1]}\n")
            self.details_text.insert(tk.END, f"User: {selected_data[2]}\n")
            self.details_text.insert(tk.END, f"Created: {selected_data[3]}\n")
            self.details_text.insert(tk.END, f"\nSOAP Note:\n")
            
            try:
                soap_data = json.loads(selected_data[4])
                self.details_text.insert(tk.END, f"SUBJECTIVE: {soap_data.get('subjective', 'N/A')}\n\n")
                self.details_text.insert(tk.END, f"OBJECTIVE: {soap_data.get('objective', 'N/A')}\n\n")
                self.details_text.insert(tk.END, f"ASSESSMENT: {soap_data.get('assessment', 'N/A')}\n\n")
                self.details_text.insert(tk.END, f"PLAN: {soap_data.get('plan', 'N/A')}\n")
            except json.JSONDecodeError:
                self.details_text.insert(tk.END, f"{selected_data[4]}\n")
    
    def refresh_current_view(self):
        """Refresh the current view"""
        if self.current_view == "users":
            self.view_users()
        elif self.current_view == "transcriptions":
            self.view_transcriptions()
        elif self.current_view == "soap_notes":
            self.view_soap_notes()
        elif self.current_view == "settings":
            self.view_settings()
    
    def run(self):
        """Start the GUI"""
        self.root.mainloop()

def main():
    """Main function"""
    try:
        viewer = DatabaseViewer()
        viewer.run()
    except Exception as e:
        print(f"Error starting database viewer: {e}")

if __name__ == "__main__":
    main()