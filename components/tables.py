import tkinter as tk
from tkinter import ttk

import customtkinter as ctk

from components.states import EmptyState, ErrorState
from utils.theme import (
    COLORS,
    FONT_FAMILY,
    RADIUS,
    SPACING,
    TABLE,
    get_font,
    resolve_color,
)

_ANCHOR = {"left": "w", "right": "e", "center": "center"}
_STICKY_WIDGET = {"left": "w", "right": "e", "center": ""}

DEFAULT_SEARCH_EMPTY_TITLE = "Tidak ada hasil"
DEFAULT_SEARCH_EMPTY_TEXT = "Coba gunakan kata kunci yang berbeda."

# Lebar area scrollbar. Header diberi jarak kanan sebesar ini pada tabel
# scrollable agar kolom header sejajar dengan kolom baris.
SCROLLBAR_GUTTER = TABLE["scrollbar_gutter"]


def text_cell(text, color=None, bold: bool = False):
    """Sel teks dengan warna/ketebalan khusus, untuk dipakai di SimpleTable.set_rows."""

    def factory(parent):
        return ctk.CTkLabel(
            parent,
            text=str(text),
            font=get_font("table_cell_bold" if bold else "table_cell"),
            text_color=color or COLORS["text"],
        )

    return factory


# ======================================================================
# SIMPLE TABLE  (tiap sel adalah widget: boleh berisi badge dan tombol)
# ======================================================================

class SimpleTable(ctk.CTkFrame):
    """
    Tabel standar aplikasi (header 40, baris 40, zebra).

    columns: list of dict
        {"title": "Nominal", "weight": 3, "align": "right"}
        align: left (default) | right (untuk angka) | center (untuk badge/aksi)

    row_height: tinggi baris (default 40; pakai 56 bila ada gambar di baris).

    scrollable=True: baris bisa digulir (header tetap di atas). Pasang tabel
    dengan pack(fill="both", expand=True).

    set_rows(rows, searching=False): rows = list of list. Setiap sel boleh:
        - teks biasa (str)
        - fungsi `lambda parent: widget` untuk badge atau tombol aksi
      searching=True menampilkan pesan "tidak ada hasil" (bukan "belum ada
      data") bila rows kosong.
      Baris dibuat bertahap: sebagian langsung tampil, sisanya menyusul,
      sehingga halaman tidak terasa tertahan.
    set_error(judul, pesan): tampilkan error state standar.

    Untuk tabel baca-saja yang besar, pakai DataTable (jauh lebih cepat).
    """

    def __init__(
        self,
        master,
        columns: list,
        empty_title: str = "Belum ada data",
        empty_text: str = "",
        scrollable: bool = False,
        row_height: int = None,
        search_empty_title: str = DEFAULT_SEARCH_EMPTY_TITLE,
        search_empty_text: str = DEFAULT_SEARCH_EMPTY_TEXT,
    ):
        super().__init__(master, fg_color="transparent")

        self.columns = columns
        self.empty_title = empty_title
        self.empty_text = empty_text
        self.search_empty_title = search_empty_title
        self.search_empty_text = search_empty_text
        self.scrollable = scrollable
        self.row_height = row_height or TABLE["row_height"]
        self._group = f"tbl{id(self)}"

        self._rows = []
        self._next_row = 0
        self._generation = 0
        self._build_job = None

        self.header = ctk.CTkFrame(
            self,
            height=TABLE["header_height"],
            corner_radius=RADIUS["small"],
            fg_color=COLORS["table_header"],
        )
        self.header.pack(
            fill="x",
            padx=(0, SCROLLBAR_GUTTER) if scrollable else 0,
        )
        self.header.grid_propagate(False)
        self._configure_columns(self.header)

        for index, column in enumerate(columns):
            align = column.get("align", "left")
            ctk.CTkLabel(
                self.header,
                text=column["title"],
                font=get_font("table_header"),
                text_color=COLORS["text_secondary"],
                anchor=_ANCHOR[align],
            ).grid(
                row=0,
                column=index,
                padx=TABLE["cell_padx"],
                sticky="ew",
            )

        if scrollable:
            self.body = ctk.CTkScrollableFrame(
                self,
                fg_color="transparent",
                corner_radius=0,
                scrollbar_button_color=COLORS["border"],
                scrollbar_button_hover_color=COLORS["text_muted"],
            )
            self.body.pack(
                fill="both",
                expand=True,
                pady=(SPACING["xs"], 0),
            )
        else:
            self.body = ctk.CTkFrame(
                self,
                fg_color="transparent",
                width=0,
                height=0,
            )
            self.body.pack(fill="x", pady=(SPACING["xs"], 0))

    def _configure_columns(self, frame):
        frame.grid_rowconfigure(0, weight=1)
        for index, column in enumerate(self.columns):
            frame.grid_columnconfigure(
                index,
                weight=column.get("weight", 1),
                uniform=self._group,
            )

    # ------------------------------------------------------------------
    # Pembuatan baris bertahap
    # ------------------------------------------------------------------
    def _cancel_build(self):
        self._generation += 1

        if self._build_job is not None:
            try:
                self.after_cancel(self._build_job)
            except Exception:
                pass

            self._build_job = None

    def _clear(self):
        self._cancel_build()

        for widget in self.body.winfo_children():
            widget.destroy()

    def destroy(self):
        self._cancel_build()
        super().destroy()

    def set_error(self, title: str, message: str = ""):
        self._clear()
        ErrorState(self.body, title, message).pack(
            fill="x",
            pady=SPACING["xl"],
        )

    def set_rows(self, rows: list, searching: bool = False):
        self._clear()

        if not rows:
            if searching:
                title, text = self.search_empty_title, self.search_empty_text
            else:
                title, text = self.empty_title, self.empty_text

            EmptyState(self.body, title, text).pack(
                fill="x",
                pady=SPACING["xl"],
            )
            return

        self._rows = rows
        self._next_row = 0

        self._build_batch(self._generation, TABLE["first_batch"])

    def _build_batch(self, generation: int, count: int):
        if generation != self._generation:
            return

        self._build_job = None

        end = min(self._next_row + count, len(self._rows))

        for position in range(self._next_row, end):
            self._build_row(position, self._rows[position])

        self._next_row = end

        if self._next_row < len(self._rows):
            self._build_job = self.after(
                1,
                self._build_batch,
                generation,
                TABLE["batch"],
            )

    def _build_row(self, position: int, values: list):
        row = ctk.CTkFrame(
            self.body,
            height=self.row_height,
            corner_radius=0,
            fg_color=(
                COLORS["table_row"]
                if position % 2 == 0
                else COLORS["table_row_alt"]
            ),
        )
        row.pack(fill="x")
        row.grid_propagate(False)
        self._configure_columns(row)

        for index, value in enumerate(values):
            align = self.columns[index].get("align", "left")

            if callable(value):
                widget = value(row)
                widget.grid(
                    row=0,
                    column=index,
                    padx=TABLE["cell_padx"],
                    sticky=_STICKY_WIDGET[align],
                )
            else:
                ctk.CTkLabel(
                    row,
                    text=str(value),
                    font=get_font("table_cell"),
                    text_color=COLORS["text"],
                    anchor=_ANCHOR[align],
                ).grid(
                    row=0,
                    column=index,
                    padx=TABLE["cell_padx"],
                    sticky="ew",
                )


# ======================================================================
# DATA TABLE  (ttk.Treeview: digambar native, cepat untuk banyak baris)
# ======================================================================

_DOT_COLORS = {
    "success": "success",
    "warning": "warning",
    "danger": "danger",
    "info": "info",
    "neutral": "text_muted",
}

DOT_SIZE = 10
DOT_COLUMN_WIDTH = 28


class DataTable(ctk.CTkFrame):
    """
    Tabel baca-saja berbasis ttk.Treeview untuk data yang banyak
    (Riwayat, Laporan). Tampilan mengikuti token tema yang sama
    dengan SimpleTable.

    Perbedaan dengan SimpleTable:
      - sel hanya berisi teks (tidak bisa memuat tombol atau badge)
      - warna per sel tidak tersedia; sebagai gantinya tiap baris dapat
        diberi titik berwarna di kolom paling kiri (show_dot=True) sesuai
        varian badge: success | warning | danger | info | neutral
      - tidak ada tombol per baris: pilih baris lalu klik dua kali / tekan
        Enter, atau baca baris terpilih lewat selected_index()

    Kolom paling kiri (show_dot=True) juga bisa berisi gambar per baris
    (mis. thumbnail barang) lewat set_rows(..., images=[...]). Gambar harus
    berupa tkinter PhotoImage / ImageTk.PhotoImage (bukan CTkImage), dan
    lebar kolomnya diatur lewat leading_width.

    Warna teks per baris: daftarkan tag lewat tag_styles, contoh
        tag_styles={"stok_habis": {"foreground": COLORS["danger"]}}
    lalu beri nama tag per baris lewat set_rows(..., tags=[...]).

    columns: sama seperti SimpleTable ({"title", "weight", "align"}).
    on_activate(index): dipanggil saat baris diklik dua kali atau Enter;
                        index = posisi baris pada daftar rows terakhir.

    set_rows(rows, variants=None, searching=False, images=None, tags=None)
        rows     : list of list (teks)
        variants : list varian per baris (opsional, untuk titik berwarna)
        images   : list gambar per baris (opsional; menggantikan titik)
        tags     : list nama tag per baris (opsional; None = tanpa tag)
    set_error(judul, pesan)
    selected_index() -> int | None
    """

    STYLE = "WH.Treeview"

    def __init__(
        self,
        master,
        columns: list,
        empty_title: str = "Belum ada data",
        empty_text: str = "",
        search_empty_title: str = DEFAULT_SEARCH_EMPTY_TITLE,
        search_empty_text: str = DEFAULT_SEARCH_EMPTY_TEXT,
        on_activate=None,
        show_dot: bool = False,
        row_height: int = None,
        leading_width: int = None,
        tag_styles: dict = None,
    ):
        super().__init__(master, fg_color="transparent")

        self.columns = columns
        self.empty_title = empty_title
        self.empty_text = empty_text
        self.search_empty_title = search_empty_title
        self.search_empty_text = search_empty_text
        self.on_activate = on_activate
        self.show_dot = show_dot

        # [GAMBAR] lebar kolom paling kiri (titik / gambar)
        self._lead_width = leading_width or DOT_COLUMN_WIDTH
        # [GAMBAR] referensi gambar agar tidak dibuang garbage collector
        self._image_refs = []

        self._state = None
        self._dots = {}
        self._column_ids = [f"c{index}" for index in range(len(columns))]

        self._apply_style(row_height or TABLE["row_height"])

        self.holder = ctk.CTkFrame(self, fg_color="transparent")
        self.holder.pack(fill="both", expand=True)
        self.holder.grid_rowconfigure(0, weight=1)
        self.holder.grid_columnconfigure(0, weight=1)

        self.tree = ttk.Treeview(
            self.holder,
            style=self.STYLE,
            columns=self._column_ids,
            show="tree headings" if show_dot else "headings",
            selectmode="browse",
            height=6,
        )
        self.tree.grid(row=0, column=0, sticky="nsew")

        scrollbar = ctk.CTkScrollbar(
            self.holder,
            command=self.tree.yview,
            button_color=COLORS["border"],
            button_hover_color=COLORS["text_muted"],
        )
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=scrollbar.set)

        if show_dot:
            self.tree.heading("#0", text="")
            self.tree.column(
                "#0",
                width=self._lead_width,
                minwidth=self._lead_width,
                stretch=False,
                anchor="center",
            )

        for column_id, column in zip(self._column_ids, columns):
            anchor = _ANCHOR[column.get("align", "left")]

            self.tree.heading(column_id, text=column["title"], anchor=anchor)
            self.tree.column(
                column_id,
                anchor=anchor,
                width=100,
                minwidth=40,
                stretch=True,
            )

        self.tree.tag_configure(
            "even",
            background=resolve_color(COLORS["table_row"]),
        )
        self.tree.tag_configure(
            "odd",
            background=resolve_color(COLORS["table_row_alt"]),
        )

        # [GAMBAR] tag warna teks per baris
        for tag_name, options in (tag_styles or {}).items():
            self.tree.tag_configure(
                tag_name,
                **{
                    key: resolve_color(value)
                    for key, value in options.items()
                },
            )

        self.tree.bind("<Double-1>", self._on_double_click)
        self.tree.bind("<Return>", self._on_return)
        self.tree.bind("<Configure>", self._on_resize)

    # ------------------------------------------------------------------
    # Style
    # ------------------------------------------------------------------
    def _scaled(self, value: int) -> int:
        try:
            return int(self._apply_widget_scaling(value))
        except Exception:
            return value

    def _apply_style(self, row_height: int):
        style = ttk.Style(self)

        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        background = resolve_color(COLORS["table_row"])
        header = resolve_color(COLORS["table_header"])
        text = resolve_color(COLORS["text"])
        muted = resolve_color(COLORS["text_secondary"])
        selected = resolve_color(COLORS["table_selected"])

        style.configure(
            self.STYLE,
            background=background,
            fieldbackground=background,
            foreground=text,
            rowheight=self._scaled(row_height),
            borderwidth=0,
            relief="flat",
            font=(FONT_FAMILY, -self._scaled(13)),
        )
        style.layout(
            self.STYLE,
            [("Treeview.treearea", {"sticky": "nswe"})],
        )
        style.map(
            self.STYLE,
            background=[("selected", selected)],
            foreground=[("selected", text)],
        )

        style.configure(
            f"{self.STYLE}.Heading",
            background=header,
            foreground=muted,
            font=(FONT_FAMILY, -self._scaled(12), "bold"),
            relief="flat",
            borderwidth=0,
            bordercolor=header,
            lightcolor=header,
            darkcolor=header,
            padding=(self._scaled(8), self._scaled(10)),
        )
        style.map(
            f"{self.STYLE}.Heading",
            background=[("active", header)],
        )

    # ------------------------------------------------------------------
    # Titik berwarna
    # ------------------------------------------------------------------
    def _dot(self, variant):
        key = variant if variant in _DOT_COLORS else "neutral"

        image = self._dots.get(key)

        if image is None:
            image = self._make_dot(
                resolve_color(COLORS[_DOT_COLORS[key]])
            )
            self._dots[key] = image

        return image

    def _make_dot(self, color: str):
        image = tk.PhotoImage(master=self, width=DOT_SIZE, height=DOT_SIZE)
        radius = DOT_SIZE / 2

        for x in range(DOT_SIZE):
            for y in range(DOT_SIZE):
                if (x + 0.5 - radius) ** 2 + (y + 0.5 - radius) ** 2 <= radius ** 2:
                    image.put(color, to=(x, y))

        return image

    # ------------------------------------------------------------------
    # Data
    # ------------------------------------------------------------------
    def _clear_state(self):
        if self._state is not None:
            self._state.destroy()
            self._state = None

        self.holder.pack_configure(fill="both", expand=True)

    def _show_state(self, state):
        self.tree.configure(height=1)
        self.holder.pack_configure(fill="x", expand=False)

        self._state = state
        self._state.pack(fill="x", pady=SPACING["xl"])

    def _clear_rows(self):
        self.tree.delete(*self.tree.get_children())

    def set_error(self, title: str, message: str = ""):
        self._clear_state()
        self._clear_rows()
        self._image_refs = []
        self._show_state(ErrorState(self, title, message))

    def set_rows(
        self,
        rows: list,
        variants: list = None,
        searching: bool = False,
        images: list = None,
        tags: list = None,
    ):
        self._clear_state()
        self._clear_rows()

        # [GAMBAR] tahan referensi gambar selama baris masih tampil
        self._image_refs = list(images) if images else []

        if not rows:
            if searching:
                title, text = self.search_empty_title, self.search_empty_text
            else:
                title, text = self.empty_title, self.empty_text

            self._show_state(EmptyState(self, title, text))
            return

        self.tree.configure(height=6)

        for index, values in enumerate(rows):
            row_tags = ["even" if index % 2 == 0 else "odd"]

            if tags and index < len(tags) and tags[index]:
                row_tags.append(tags[index])

            options = {
                "iid": str(index),
                "text": "",
                "values": [str(value) for value in values],
                "tags": tuple(row_tags),
            }

            if self.show_dot:
                image = (
                    images[index]
                    if images and index < len(images)
                    else None
                )

                if image is None:
                    variant = (
                        variants[index]
                        if variants and index < len(variants)
                        else None
                    )
                    image = self._dot(variant)

                options["image"] = image

            self.tree.insert("", "end", **options)

    def selected_index(self):
        selection = self.tree.selection()

        if not selection:
            return None

        try:
            return int(selection[0])
        except (TypeError, ValueError):
            return None

    # ------------------------------------------------------------------
    # Event
    # ------------------------------------------------------------------
    def _on_double_click(self, event):
        item = self.tree.identify_row(event.y)

        if not item:
            return

        self.tree.selection_set(item)
        self._activate(item)

    def _on_return(self, _event):
        selection = self.tree.selection()

        if selection:
            self._activate(selection[0])

        return "break"

    def _activate(self, item):
        if not self.on_activate:
            return

        try:
            self.on_activate(int(item))
        except (TypeError, ValueError):
            pass

    def _on_resize(self, event):
        total = event.width - (self._lead_width if self.show_dot else 0)

        if total <= 0:
            return

        weights = sum(column.get("weight", 1) for column in self.columns)

        for column_id, column in zip(self._column_ids, self.columns):
            share = column.get("weight", 1) / weights
            self.tree.column(column_id, width=max(40, int(total * share)))