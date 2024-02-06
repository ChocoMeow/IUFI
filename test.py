SHOP_BASE: list[tuple[str, str, int]] = [
    ("🌹", "roll.rare", 30),
    ("🌹", "roll.epic", 100),
    ("🌹", "roll.legendary", 250)
]

VALENTINE_ITEMS: list[tuple[str, str, int]] = [
    ("🌹", "event_item.rose", 10)
]

SHOP_BASE.extend(VALENTINE_ITEMS)
print(SHOP_BASE)

SHOP_BASE.remove(VALENTINE_ITEMS[0])
print(SHOP_BASE)

