import customtkinter as ctk

from utils.theme import (
    BUTTON_HEIGHT,
    COLORS,
    DIALOG_PADDING,
    DIALOG_WIDTH,
    INPUT_HEIGHT,
    RADIUS,
    SPACING,
    button_style,
    get_font,
)

# Lebar teks di dalam dialog form (lebar dialog dikurangi padding kiri-kanan).
FORM_TEXT_WIDTH = DIALOG_WIDTH["form"] - (DIALOG_PADDING * 2)


def entry_style() -> dict:
    """Kwargs standar untuk ctk.CTkEntry (tinggi 36, radius 8, border 1px)."""
    return {
        "height": INPUT_HEIGHT,
        "corner_radius": RADIUS["input"],
        "border_width": 1,
        "border_color": COLORS["border"],
        "fg_color": COLORS["surface"],
        "text_color": COLORS["text"],
        "placeholder_text_color": COLORS["text_muted"],
        "font": get_font("body"),
    }


def option_menu_style() -> dict:
    """Kwargs standar untuk ctk.CTkOptionMenu (tinggi sama dengan input)."""
    return {
        "height": INPUT_HEIGHT,
        "corner_radius": RADIUS["input"],
        "fg_color": COLORS["surface_hover"],
        "button_color": COLORS["border"],
        "button_hover_color": COLORS["text_muted"],
        "text_color": COLORS["text"],
        "font": get_font("body"),
        "dropdown_fg_color": COLORS["surface"],
        "dropdown_hover_color": COLORS["surface_hover"],
        "dropdown_text_color": COLORS["text"],
        "dropdown_font": get_font("body"),
    }


def apply_focus_ring(entry):
    """Border input berubah menjadi warna primary saat fokus."""

    def on_focus_in(_event):
        try:
            entry.configure(border_color=COLORS["primary"])
        except Exception:
            pass

    def on_focus_out(_event):
        try:
            entry.configure(border_color=COLORS["border"])
        except Exception:
            pass

    entry.bind("<FocusIn>", on_focus_in, add="+")
    entry.bind("<FocusOut>", on_focus_out, add="+")


class FormLabel(ctk.CTkLabel):
    """Label field standar (di atas input)."""

    def __init__(self, master, text: str, required: bool = False):
        super().__init__(
            master,
            text=f"{text} *" if required else text,
            font=get_font("label"),
            text_color=COLORS["text"],
            anchor="w",
        )


class FormField(ctk.CTkFrame):
    """
    Field form standar:

        Label
        [ Input                         ]

    Contoh:
        field = FormField(parent, "Nama", "Masukkan nama", required=True)
        field.pack(fill="x")
        field.get()
    """

    def __init__(
        self,
        master,
        label: str,
        placeholder: str = "",
        initial: str = "",
        required: bool = False,
    ):
        super().__init__(master, fg_color="transparent")

        FormLabel(self, label, required).pack(fill="x")

        self.entry = ctk.CTkEntry(
            self,
            placeholder_text=placeholder,
            **entry_style(),
        )
        self.entry.pack(fill="x", pady=(SPACING["xs"], 0))
        apply_focus_ring(self.entry)

        if initial:
            self.entry.insert(0, initial)

    def get(self) -> str:
        return self.entry.get()

    def set(self, value: str):
        self.entry.delete(0, "end")
        self.entry.insert(0, value)

    def focus(self):
        self.entry.focus()


class ReadOnlyField(ctk.CTkFrame):
    """
    Field hanya-baca dengan tinggi sama seperti input:

        Label
        [ Nilai                         ]
    """

    def __init__(
        self,
        master,
        label: str,
        value: str = "-",
        bold: bool = False,
    ):
        super().__init__(master, fg_color="transparent")

        FormLabel(self, label).pack(fill="x")

        box = ctk.CTkFrame(
            self,
            height=INPUT_HEIGHT,
            fg_color=COLORS["surface_hover"],
            corner_radius=RADIUS["input"],
        )
        box.pack(fill="x", pady=(SPACING["xs"], 0))
        box.pack_propagate(False)

        self.value_label = ctk.CTkLabel(
            box,
            text=value,
            font=get_font("button" if bold else "body"),
            text_color=COLORS["text"],
            anchor="w",
        )
        self.value_label.pack(
            fill="both",
            expand=True,
            padx=SPACING["md"],
        )

    def set(self, text: str, color=None):
        self.value_label.configure(
            text=text,
            text_color=color or COLORS["text"],
        )


class FilterField(ctk.CTkFrame):
    """
    Label kecil di atas satu kontrol (untuk bar filter).
    Pasang kontrol di `field.body`, contoh:

        field = FilterField(bar, "Jenis")
        ctk.CTkOptionMenu(field.body, ...).pack(fill="x")
    """

    def __init__(self, master, label: str):
        super().__init__(master, fg_color="transparent", width=0, height=0)

        FormLabel(self, label).pack(fill="x")

        self.body = ctk.CTkFrame(
            self,
            fg_color="transparent",
            width=0,
            height=0,
        )
        self.body.pack(fill="x", pady=(SPACING["xs"], 0))


class ErrorText(ctk.CTkLabel):
    """Teks error di bawah form. show(pesan) untuk menampilkan, clear() untuk menghapus."""

    def __init__(self, master, wraplength: int = FORM_TEXT_WIDTH):
        super().__init__(
            master,
            text="",
            font=get_font("small"),
            text_color=COLORS["danger"],
            anchor="w",
            justify="left",
            wraplength=wraplength,
        )

    def show(self, message: str):
        self.configure(text=message)

    def clear(self):
        self.configure(text="")


class SearchBar(ctk.CTkEntry):
    """
    Search bar standar (tinggi 36, lebar 320) untuk semua halaman.
 
    textvariable tetap bisa dipakai pemanggil (get(), trace_add("write")),
    tetapi TIDAK diteruskan ke CTkEntry: CustomTkinter tidak menampilkan
    placeholder bila entry memakai textvariable. Isi entry disalin ke
    variabel itu secara manual, dan sebaliknya.
    """
 
    def __init__(
        self,
        master,
        textvariable,
        placeholder: str = "Cari...",
        width: int = 320,
    ):
        super().__init__(
            master,
            placeholder_text=f"🔍  {placeholder}",
            width=width,
            **entry_style(),
        )
 
        self._var = textvariable
        self._syncing = False
 
        # Ketik/hapus: teks sudah berubah saat KeyRelease.
        self.bind("<KeyRelease>", lambda _e: self._sync_to_var())
 
        # Tempel/potong/hapus pilihan: teks baru berubah setelah event ini.
        for sequence in ("<<Paste>>", "<<Cut>>", "<<Clear>>"):
            self.bind(sequence, lambda _e: self.after_idle(self._sync_to_var))
 
        self._var.trace_add("write", self._sync_from_var)
 
        if self._var.get():
            self._replace_text(self._var.get())
 
    # Perubahan lewat kode (mis. entry.delete(0, "end")) ikut disalin.
    def delete(self, *args, **kwargs):
        super().delete(*args, **kwargs)
        self._sync_to_var()
 
    def insert(self, *args, **kwargs):
        super().insert(*args, **kwargs)
        self._sync_to_var()
 
    def _sync_to_var(self):
        if self._syncing:
            return
 
        value = self.get()
 
        if self._var.get() != value:
            self._syncing = True
 
            try:
                self._var.set(value)
            finally:
                self._syncing = False
 
    def _sync_from_var(self, *_args):
        if self._syncing:
            return
 
        try:
            value = self._var.get()
 
            if value != self.get():
                self._replace_text(value)
        except Exception:
            # Widget sudah ditutup sementara variabel masih hidup.
            pass
 
    def _replace_text(self, value: str):
        self._syncing = True
 
        try:
            super().delete(0, "end")
 
            if value:
                super().insert(0, value)
        finally:
            self._syncing = False

class QtyStepper(ctk.CTkFrame):
    """
    Pengatur jumlah di dalam tabel:  [−] [ qty ] [+]

        on_step(delta)  : dipanggil dengan -1 atau +1
        on_set(teks)    : bila diberikan, qty berupa kolom ketik dan
                          dipanggil saat Enter; bila tidak, qty hanya teks.

    Validasi (stok, angka) tetap dilakukan oleh halaman.
    """

    def __init__(self, master, quantity, on_step, on_set=None):
        super().__init__(master, fg_color="transparent", width=0, height=0)

        ctk.CTkButton(
            self,
            text="−",
            width=BUTTON_HEIGHT["small"],
            command=lambda: on_step(-1),
            **button_style("secondary", "small"),
        ).pack(side="left")

        if on_set is not None:
            style = entry_style()
            style["height"] = BUTTON_HEIGHT["small"]

            self.entry = ctk.CTkEntry(
                self,
                width=56,
                justify="center",
                **style,
            )
            self.entry.insert(0, str(quantity))
            self.entry.bind("<Return>", lambda _event: on_set(self.entry.get()))
            self.entry.pack(side="left", padx=SPACING["xs"])
            apply_focus_ring(self.entry)
        else:
            ctk.CTkLabel(
                self,
                text=str(quantity),
                width=36,
                anchor="center",
                font=get_font("button"),
                text_color=COLORS["text"],
            ).pack(side="left", padx=SPACING["xs"])

        ctk.CTkButton(
            self,
            text="+",
            width=BUTTON_HEIGHT["small"],
            command=lambda: on_step(1),
            **button_style("secondary", "small"),
        ).pack(side="left")


class InfoRow(ctk.CTkFrame):
    """Baris info untuk dialog detail: label di kiri, nilai di kanan."""

    def __init__(
        self,
        master,
        label: str,
        value: str,
        bold: bool = False,
        wraplength: int = 320,
        color=None,
    ):
        super().__init__(master, fg_color="transparent")

        self.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            self,
            text=label,
            font=get_font("body"),
            text_color=COLORS["text_secondary"],
            anchor="w",
        ).grid(row=0, column=0, sticky="w")

        ctk.CTkLabel(
            self,
            text=value,
            font=get_font("subheading" if bold else "body"),
            text_color=color or COLORS["text"],
            anchor="e",
            justify="right",
            wraplength=wraplength,
        ).grid(row=0, column=1, sticky="e", padx=(SPACING["xl"], 0))