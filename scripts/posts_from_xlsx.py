import pandas as pd
import openpyxl

archivo = "todos.xlsx"
skip_row = 10
columna = 12

# Escribe el valor del hipervínculo en la celda
wb = openpyxl.load_workbook(archivo)
ws = wb['Top 10 Posts']
for row in ws.iter_rows(min_row=skip_row, min_col=columna, max_col=columna):
    for cell in row:
        try:
            # print(cell.hyperlink.target)
            cell.value = cell.hyperlink.target
        except AttributeError:
            pass
wb.save(archivo)

# Carga el archivo con pandas
posteos = pd.read_excel(archivo, skiprows=skip_row)
posteos = posteos.loc[posteos['Network'] == "FACEBOOK"]
posteos = posteos.drop("Network", axis=1)
posteos = posteos[["Page", "Link"]]

# Reemplazar nombres de las páginas por sus usuarios de ig
posteos["Page"] = ["santander" if "Santander" in p else p for p in posteos["Page"]]
posteos["Page"] = ["bancociudad" if "Ciudad" in p else p for p in posteos["Page"]]
posteos["Page"] = ["bancoprovincia" if "Provincia" in p else p for p in posteos["Page"]]


# Genera los archivos txt con los posteos de cada usuario
for p in posteos["Page"]:
    links = posteos.loc[posteos["Page"] == p]["Link"].tolist()
    file = f"./posts/{p}.txt"
    with open(file, "w") as f:
        for link in links:
            f.write(f"{link}\n")