def is_malayalam(text: str) -> bool:
  return all('\u0D00' <= char <= '\u0D7F' or char.isspace() or char in ",.!?:" for char in text)

def generate_short_id(sheet) -> str:
  dialogue_ids = sheet.col_values(5)[1:]  # skip header
  numeric_ids = [int(d_id) for d_id in dialogue_ids if d_id.isdigit()]

  if not numeric_ids:
      return "1"
  else:
      last_id = max(numeric_ids)
      return str(last_id + 1)
