from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder, KeyboardButton
from aiogram.types import InlineKeyboardMarkup, ReplyKeyboardMarkup
from typing import List, Dict, Union

# This file contains all the keyboard layouts for the bot.
# The use of builders allows for flexible and dynamic keyboard creation.

def get_main_menu() -> ReplyKeyboardMarkup:
    """
    Builds the main, persistent reply keyboard.
    Layout is designed for quick access to primary functions, with a logical grouping.
    'Crea Annuncio' gets its own row for prominence.
    """
    builder = ReplyKeyboardBuilder()
    builder.button(text="🆕 Crea Annuncio")
    builder.row(
        KeyboardButton(text="🛍️ I Miei Annunci"),
        KeyboardButton(text="✅ Segna Venduto")
    )
    builder.row(
        KeyboardButton(text="📊 Statistiche"),
        KeyboardButton(text="💎 Abbonamenti")
    )
    builder.row(
        KeyboardButton(text="👤 Profilo"),
        KeyboardButton(text="❓ Aiuto")
    )
    return builder.as_markup(resize_keyboard=True)

def get_ad_manage_kb(ad_id: int, status: str) -> InlineKeyboardMarkup:
    """
    Builds an inline keyboard for managing a specific ad.
    The layout is contextual, grouping buttons logically and hiding non-applicable actions.
    """
    builder = InlineKeyboardBuilder()
    
    # Core actions
    builder.button(text="ℹ️ Dettagli", callback_data=f"view_details:{ad_id}")
    builder.button(text="✏️ Modifica", callback_data=f"edit_ad:{ad_id}")
    
    # Status-dependent actions
    # 'Bozza' is the Italian for 'DRAFT' used in the handler
    if status in ['Bozza', 'DRAFT']:
        builder.button(text="📅 Pubblica", callback_data=f"publish_ad:{ad_id}")
    
    if status != 'SOLD':
        # This now uses the correct callback data to trigger the existing FSM
        builder.button(text="✅ Segna Venduto", callback_data=f"sell_select:{ad_id}")

    # Destructive action is always available
    builder.button(text="🗑️ Elimina", callback_data=f"delete_ad:{ad_id}")
    
    # Adjust layout for a clean 2-column grid
    builder.adjust(2)
    return builder.as_markup()

def get_edit_menu_kb(ad_id: int) -> InlineKeyboardMarkup:
    """
    Builds an inline keyboard for editing the specific fields of an ad.
    This provides a clear, focused interface for the modification process.
    The 'Finish' button is on its own row for emphasis.
    """
    builder = InlineKeyboardBuilder()
    builder.button(text="Titolo", callback_data=f"edit_field_title:{ad_id}")
    builder.button(text="Descrizione", callback_data=f"edit_field_description:{ad_id}")
    builder.button(text="Prezzo", callback_data=f"edit_field_price:{ad_id}")
    builder.button(text="↩️ Ho Fatto / Anteprima", callback_data=f"finish_edit:{ad_id}")
    builder.adjust(3, 1)
    return builder.as_markup()

def get_subscription_kb(plans_list: List[Dict[str, Union[str, int]]]) -> InlineKeyboardMarkup:
    """
    Builds an inline keyboard with available subscription plans.
    The plans are generated dynamically based on the input list, making it easy to add or change plans.
    A 'Back' button and an 'Info' button are included for easy navigation and information access.
    """
    builder = InlineKeyboardBuilder()
    builder.button(text="ℹ️ Info Piani", callback_data="sub_info")
    for plan in plans_list:
        builder.button(text=f"💎 {plan['name']} - {plan['price_euro']}€", callback_data=f"sub:{plan['id_account_type']}")
    
    builder.button(text="🔙 Torna al Menu", callback_data="main_menu")
    builder.adjust(1) # One button per row for clarity
    return builder.as_markup()

def get_categories_kb(categories: List[Dict[str, Union[str, int]]]) -> InlineKeyboardMarkup:
    """
    Builds a dynamic grid of categories for selection.
    The 2-column layout is efficient for displaying a medium number of options without
    taking up too much vertical space.
    """
    builder = InlineKeyboardBuilder()
    for category in categories:
        builder.button(text=category['name'], callback_data=f"cat:{category['id_category']}")
    
    builder.adjust(2)
    return builder.as_markup()

def get_platforms_kb(platforms: List[Dict[str, Union[str, int]]]) -> InlineKeyboardMarkup:
    """
    Builds a dynamic grid of platforms.
    The layout uses 2 columns and adds a final, full-width button to skip the step,
    providing a clear escape path for the user.
    """
    builder = InlineKeyboardBuilder()
    for platform in platforms:
        builder.button(text=platform['name'], callback_data=f"platform:{platform['id_platform']}")
    
    builder.button(text="⏭️ Salta / Salva in Bozza", callback_data="skip_platform")
    
    # Adjust layout to have 2 columns for platforms and 1 column for the skip button
    num_platforms = len(platforms)
    adjust_params = [2] * (num_platforms // 2)
    if num_platforms % 2 != 0:
        adjust_params.append(1)
    adjust_params.append(1) # For the skip button
    builder.adjust(*adjust_params)

    return builder.as_markup()

def get_profile_kb() -> InlineKeyboardMarkup:
    """
    Builds the inline keyboard for the user profile section.
    This groups user-specific financial and account management actions together.
    A 'Back' button is included for easy navigation.
    """
    builder = InlineKeyboardBuilder()
    builder.button(text="💳 Ricarica Crediti", callback_data="recharge_credits")
    builder.button(text="📜 Storico Pagamenti", callback_data="payment_history")
    builder.button(text="🔙 Torna al Menu", callback_data="main_menu")
    builder.adjust(1) # One action per row for clarity
    return builder.as_markup()

def get_confirmation_kb(action: str, target_id: int) -> InlineKeyboardMarkup:
    """
    Builds a universal confirmation keyboard.
    The affirmative action is placed on the left, which is a common UX pattern.
    Callback data includes both the action and target ID for a clear, stateful response.
    """
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Conferma", callback_data=f"confirm_{action}:{target_id}")
    builder.button(text="❌ Annulla", callback_data=f"cancel_{action}:{target_id}")
    return builder.as_markup()
