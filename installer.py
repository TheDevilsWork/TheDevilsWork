from asarPy import pack_asar, extract_asar
import os, sys, zipfile, json
import tkinter as tk
import tkinter.ttk as ttk
import tkinter.messagebox, tkinter.filedialog
from shutil import rmtree, copyfile, move
import diff_match_patch as dmp_module

version = "1.0"

def doError(msg):
	tk.messagebox.showerror("Error", msg)

def config_save(key, value):
	global config, initialdir
	try:
		olddir = os.getcwd()
		if os.getcwd() != initialdir:
			os.chdir(initialdir)
		if not config:
			config = {}
		if key and value:
			if key in config and config[key] == value:
				return
			config[key] = value
		with open("tdw_config.json", "w") as config_file:
			json.dump(config, config_file)
	finally:
		if olddir != os.getcwd():
			os.chdir(olddir)

def on_close():
	global window
	config_save("lastheight", window.winfo_height())
	config_save("lastwidth", window.winfo_width())
	config_save("lastsave", savefile)
	window.destroy()

def config_load():
	global config, initialdir
	try:
		olddir = os.getcwd()
		if os.getcwd() != initialdir:
			os.chdir(initialdir)
		if not os.path.exists("tdw_config.json"):
			config = {}
			return
		with open("tdw_config.json", "r") as config_file:
			try:
				config = json.load(config_file)
			except:
				pass
	finally:
		if olddir != os.getcwd():
			os.chdir(olddir)

def config_get(key):
	global config
	if not config or key not in config:
		return None
	return config[key]

def save_select():
	global savefile
	new_savefile = tk.filedialog.asksaveasfilename( defaultextension='.json', filetypes=[("JSON file", "*.json")] )
	if not new_savefile:
		return
	savefile = new_savefile
	save_mods()
	config_save("lastsave", savefile)

def save_mods():
	global savefile, lb_files, disabled
	if not savefile:
		return
	with open(savefile, "w") as save:
		json.dump({ "mods": lb_files.get(0, tk.END), "disabled" : list(disabled)}, save)

def load_mods():
	global savefile, disabled
	if not savefile:
		return
	with open(savefile, "r") as save:
		try:
			loaded_save = json.load(save)
		except:
			return
		clear_mods()
		if "mods" in loaded_save and len(loaded_save["mods"]):
			add_mods(loaded_save["mods"])
		if "disabled" in loaded_save and len(loaded_save["disabled"]):
			disabled = set(loaded_save["disabled"])
		updateFileList()

def clear_mods():
	global lb_files
	lb_files.delete(0, tk.END)
	
def load_select():
	global savefile
	new_savefile = tk.filedialog.askopenfilename( filetypes=[("JSON file", "*.json")] )
	if not new_savefile:
		return
	savefile = new_savefile
	load_mods()

def resource_path(relative_path):	
	try:	   
		base_path = sys._MEIPASS
	except Exception:
		base_path = os.path.abspath(".")
	return os.path.join(base_path, relative_path)

class AutoScrollbar(tk.Scrollbar):
	"""Create a scrollbar that hides iteself if it's not needed. Only
	works if you use the pack geometry manager from tkinter.
	"""
	def set(self, lo, hi):
		if float(lo) <= 0.0 and float(hi) >= 1.0:
			self.pack_forget()
		else:
			if self.cget("orient") == tk.HORIZONTAL:
				self.pack(fill=tk.BOTH, side=tk.BOTTOM)
			else:
				self.pack(fill=tk.BOTH, side=tk.RIGHT)
		tk.Scrollbar.set(self, lo, hi)
	def grid(self, **kw):
		raise tk.TclError("cannot use grid with this widget")
	def place(self, **kw):
		raise tk.TclError("cannot use place with this widget")

class ReorderableListbox(tk.Listbox):
	""" A Tkinter listbox with drag & drop reordering of lines """
	def __init__(self, master, **kw):
		kw['selectmode'] = tk.EXTENDED
		tk.Listbox.__init__(self, master, kw)
		self.bind('<Button-1>', self.setCurrent)
		self.bind('<Control-1>', self.toggleSelection)
		self.bind('<B1-Motion>', self.shiftSelection)
		self.bind('<BackSpace>', self.deleteSelection)
		self.bind('<Leave>',  self.onLeave)
		self.bind('<Enter>',  self.onEnter)
		self.selectionClicked = False
		self.left = False
		self.unlockShifting()
		self.ctrlClicked = False
	def orderChangedEventHandler(self):
		pass

	def onLeave(self, event):
		# prevents changing selection when dragging
		# already selected items beyond the edge of the listbox
		if self.selectionClicked:
			self.left = True
			return 'break'
	def onEnter(self, event):
		#TODO
		self.left = False

	def setCurrent(self, event):
		self.ctrlClicked = False
		i = self.nearest(event.y)
		self.selectionClicked = self.selection_includes(i)
		if (self.selectionClicked):
			return 'break'

	def toggleSelection(self, event):
		self.ctrlClicked = True
	
	def deleteSelection(self, event):
		for index in sorted(self.curselection(), reverse=True): # reverse so we don't disturb the ordering
			if self.get(index) in disabled:
				disabled.remove(self.get(index))
			self.delete(index)

	def moveElement(self, source, target):
		if not self.ctrlClicked:
			element = self.get(source)
			self.delete(source)
			self.insert(target, element)

	def unlockShifting(self):
		self.shifting = False
	def lockShifting(self):
		# prevent moving processes from disturbing each other
		# and prevent scrolling too fast
		# when dragged to the top/bottom of visible area
		self.shifting = True

	def shiftSelection(self, event):
		if self.ctrlClicked:
			return
		selection = self.curselection()
		if not self.selectionClicked or len(selection) == 0:
			return

		selectionRange = range(min(selection), max(selection))
		currentIndex = self.nearest(event.y)

		if self.shifting:
			return 'break'

		lineHeight = 15
		bottomY = self.winfo_height()
		if event.y >= bottomY - lineHeight:
			self.lockShifting()
			self.see(self.nearest(bottomY - lineHeight) + 1)
			self.master.after(500, self.unlockShifting)
		if event.y <= lineHeight:
			self.lockShifting()
			self.see(self.nearest(lineHeight) - 1)
			self.master.after(500, self.unlockShifting)

		if currentIndex < min(selection):
			self.lockShifting()
			notInSelectionIndex = 0
			for i in selectionRange[::-1]:
				if not self.selection_includes(i):
					self.moveElement(i, max(selection)-notInSelectionIndex)
					notInSelectionIndex += 1
			currentIndex = min(selection)-1
			self.moveElement(currentIndex, currentIndex + len(selection))
			self.orderChangedEventHandler()
		elif currentIndex > max(selection):
			self.lockShifting()
			notInSelectionIndex = 0
			for i in selectionRange:
				if not self.selection_includes(i):
					self.moveElement(i, min(selection)+notInSelectionIndex)
					notInSelectionIndex += 1
			currentIndex = max(selection)+1
			self.moveElement(currentIndex, currentIndex - len(selection))
			self.orderChangedEventHandler()
		self.unlockShifting()
		updateFileList()
		return 'break'

def updateFileList():
	global window, lb_files, disabled
	filelist = lb_files.get(0, tk.END)
	for i in range(len(filelist)):
		if filelist[i] in disabled:
			lb_files.itemconfigure(i, bg = "red", fg = "white", selectbackground = "#ff7979")
		else:
			lb_files.itemconfigure(i, bg = "white", fg = "black", selectbackground = "#0066CC")

def toggle_mod(self):
	global lb_files, disabled
	selected_pos = set(lb_files.curselection())
	if not len(selected_pos):
		return
	disabled.symmetric_difference_update(set(map(lambda x : lb_files.get(x), selected_pos)))
	updateFileList()

def patchFile(file_to_patch, diff_to_patch):
	global dmp
	with open(file_to_patch, "r+", encoding="utf-8") as file:
		text1 = file.read()
		file.seek(0)
		text2, _ = dmp.patch_apply(
			dmp.patch_fromText(
				diff_to_patch
			),
			text1
		)
		file.write(text2)
		file.truncate()

def main():
	global window, close_on_launch, version, lb_files, filelist, disabled, dmp, config, savefile, initialdir
	
	initialdir = os.getcwd()
	
	config_load()
	
	our_height = config_get("lastheight") or 200
	our_width = config_get("lastwidth") or 500
	
	dmp = dmp_module.diff_match_patch()
	
	window = tk.Tk()
	window.title("The Devil's Work v%s" % version)
	window.iconbitmap(resource_path(r'TheDevilsWork.ico'))
	window.geometry("%dx%d" % (our_width, our_height))
	window.rowconfigure(0, weight=0)
	window.rowconfigure(1, weight=1, minsize=75)
	window.columnconfigure(0, weight=1, minsize=500)
	
	gamedir = sys.argv[1] if len(sys.argv) >= 2 else config_get("gamedir")
	if gamedir:
		setdir(gamedir)
	
	fr_text = ttk.Frame(window)
	fr_text.rowconfigure(0, weight=0)
	fr_text.rowconfigure(1, weight=0)
	fr_text.columnconfigure(0, weight=1)
	lbl_id = ttk.Label(fr_text, text="The Devil's Work v%s" % version, font=("Arial", 24, "bold"), anchor = tk.CENTER)
	lbl_info = ttk.Label(fr_text, text="A We Know The Devil mod installer", font=("Arial", 10, "italic"), anchor = tk.CENTER)
	lbl_id.grid(row=0, column=0, sticky="ew")
	lbl_info.grid(row=1, column=0, sticky="ew")
	fr_text.grid(row=0, column=0, sticky="nsew")
	
	fr_controls = ttk.Frame(window)
	fr_controls.rowconfigure(0, weight=1)
	fr_controls.rowconfigure(1, weight=0)
	fr_controls.columnconfigure(0, weight=1)
	
	disabled = set()
	fr_files = ttk.LabelFrame(fr_controls, text = "Mods")
	fr_files.rowconfigure(0, weight=1, minsize = 25)
	fr_files.rowconfigure(1, weight=0, minsize = 25)
	fr_files.columnconfigure(0, weight=1)
	fr_filebuttons = ttk.Frame(fr_files)
	fr_filebuttons.rowconfigure(0, weight=0)
	fr_filebuttons.columnconfigure([0, 1, 2, 3], weight=1)
	btn_open = ttk.Button(fr_filebuttons, text="Add Mod", command=mod_select)
	btn_open.grid(row=0, column=0, padx=5, pady=5)
	btn_install = ttk.Button(fr_filebuttons, text="Install Mods", command=install_all)
	btn_install.grid(row=0, column=1)
	btn_save = ttk.Button(fr_filebuttons, text="Save Modlist", command=save_select)
	btn_save.grid(row=0, column=2, padx=5, pady=5)
	btn_load = ttk.Button(fr_filebuttons, text="Load Modlist", command=load_select)
	btn_load.grid(row=0, column=3, padx=5, pady=5)
	lb_files = ReorderableListbox(fr_files)
	lb_files.bind('<Double-Button-1>', toggle_mod)
	lb_files.grid(row=0, column=0, sticky="nsew")
	scrollv = AutoScrollbar(lb_files)
	scrollv.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
	lb_files.config(yscrollcommand = scrollv.set)
	scrollv.config(command = lb_files.yview)
	scrollh = AutoScrollbar(lb_files, orient="horizontal")
	scrollh.pack(side=tk.BOTTOM, expand=True)
	lb_files.config(xscrollcommand = scrollh.set)
	scrollh.config(command = lb_files.xview)
	fr_filebuttons.grid(row=1, column=0, sticky="ns")
	
	fr_buttons = ttk.Frame(fr_controls)
	fr_buttons.rowconfigure(0, weight=1) # minsize = 800
	fr_buttons.columnconfigure([0, 1, 2, 3], weight=1)
	btn_directory = ttk.Button(fr_buttons, text="Find WKTD", command=setdir)
	btn_uninstall = ttk.Button(fr_buttons, text="Uninstall All Mods", command=uninstall)
	btn_start = ttk.Button(fr_buttons, text="Launch WKTD", command=launch)
	close_on_launch = tk.IntVar()
	chk_close = ttk.Checkbutton(fr_buttons, text='Close Installer On Launch',variable=close_on_launch, onvalue=1, offvalue=0)
	
	btn_directory.grid(row=0, column=0, padx=5, pady=5)
	btn_uninstall.grid(row=0, column=1, padx=5, pady=5)
	btn_start.grid(row=0, column=2, padx=5, pady=5)
	chk_close.grid(row=0, column=3, padx=5, pady=5)

	fr_files.grid(row=0, column=0, sticky="nsew")
	fr_buttons.grid(row=1, column=0, sticky="ns")
	
	fr_controls.grid(row=1, column=0, sticky="nsew")
	
	window.update()
	window.minsize(500, 200)
	
	window.protocol("WM_DELETE_WINDOW", on_close)
	
	savefile = config_get("lastsave")
	if savefile:
		load_mods()
	
	window.mainloop()

def setdir(newdir = None):
	if not newdir:
		newdir = tk.filedialog.askdirectory()
	if not newdir or not os.path.exists(newdir) or not os.path.exists("%s/%s" % (newdir, r'We Know the Devil.exe')):
		return
	os.chdir(newdir)
	config_save("gamedir", newdir)

def launch():
	global close_on_launch
	if not os.path.exists(r'We Know the Devil.exe'):
		doError("Could not find 'We Know the Devil.exe', is the executable in the right directory?")
		return
	os.startfile(r'We Know the Devil.exe')
	if close_on_launch.get():
		window.destroy()

def mod_select():
	modpaths = tk.filedialog.askopenfilenames(
		filetypes=[("ZIP archives", "*.zip"), ("All Files", "*.*")]
	)
	add_mods(modpaths)

def add_mods(modlist):
	global lb_files
	for mod in modlist:
		if os.path.exists(mod):
			lb_files.insert(tk.END, mod)
	updateFileList()

def uninstall():
	if not os.path.exists("./resources/app.asar.old"):
		doError("Unable to uninstall mods, could not locate app.asar.old! Is this a modded installation?")
		return
	copyfile("./resources/app.asar.old", "./resources/app.asar")
	tk.messagebox.showinfo("Uninstalled", "Mods uninstalled.")
	return

def install_all():
	global lb_files, disabled
	try:
		window.tk.call('tk', 'busy', 'hold', window)
		if not os.path.exists("./resources/app.asar") and not os.path.exists("./resources/app.asar.old"):
			tk.messagebox.showwarning("Warning", "This executable must be placed in the main WKTD game directory!")
			return
		if not os.path.exists("./resources/app.asar.old"):
			if not move("./resources/app.asar", "./resources/app.asar.old"):
				doError("Unable to move app.asar to backup, try running as administrator!")
				return
		window.update()
		extract_asar("./resources/app.asar.old", "temp_mod")
		for modpath in [x for x in lb_files.get(0, tk.END) if x not in disabled]:
			if not os.path.exists(modpath):
				doError("Unable to find '%s'." % modpath)
				return
			with zipfile.ZipFile(modpath, 'r') as modzip:
				for filepath in modzip.namelist():
					window.update()
					fname, fext = os.path.splitext(filepath)
					if fext == ".patch":
						with modzip.open(filepath, 'r') as f:
							patchFile("temp_mod/%s" % fname, str(f.read(), encoding = "utf-8"))
					else:
						modzip.extract(filepath, "temp_mod")
			
		pack_asar("temp_mod", "./resources/app.asar")
		window.tk.call('tk', 'busy', 'forget', window)
		window.update()
		tk.messagebox.showinfo("Installation Complete", "Mod installation complete!")
	finally:
		if window.tk.call('tk', 'busy', 'status', window):
			window.tk.call('tk', 'busy', 'forget', window)
			window.update()
		if os.path.exists("./temp_mod"):
			rmtree("./temp_mod")