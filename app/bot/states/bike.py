"""FSM state groups for bike management flows."""

from aiogram.fsm.state import State, StatesGroup


class AddBikeForm(StatesGroup):
    """Multi-step form for adding a new bike."""

    bike_number = State()
    model = State()
    store = State()
    commissioned_at = State()
    confirm = State()


class TakeBikeForm(StatesGroup):
    """Multi-step form for taking a bike on shift."""

    store = State()
    bike = State()
    courier_search = State()  # text input: search by name/surname
    courier = State()
    confirm = State()


class BreakdownForm(StatesGroup):
    """Multi-step form for creating a breakdown card."""

    store = State()
    bike = State()
    breakdown_type = State()
    description = State()
    photos = State()
    courier = State()
    confirm = State()


class RepairPickupForm(StatesGroup):
    """FSM for mechanic picking up a bike for repair."""

    store = State()
    bike = State()
    breakdown = State()
    mechanic = State()
    confirm = State()


class RepairCompleteForm(StatesGroup):
    """FSM for mechanic completing a repair."""

    repair = State()
    work_description = State()
    duration = State()
    cost = State()
    confirm = State()


class RegistrationForm(StatesGroup):
    """FSM for new user registration."""

    name = State()


class CourierShiftForm(StatesGroup):
    """FSM for courier taking a bike on shift."""

    bike_number = State()
    confirm = State()
