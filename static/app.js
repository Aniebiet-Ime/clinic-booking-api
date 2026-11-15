const api = {
  async getSlots(provider = '') {
    const query = provider ? `?provider=${encodeURIComponent(provider)}` : '';
    const response = await fetch(`/api/ui/slots${query}`);
    if (!response.ok) throw new Error('Unable to load slots');
    const payload = await response.json();
    return payload.slots || [];
  },

  async createBooking(data) {
    const response = await fetch('/api/ui/bookings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.error || 'Booking failed');
    }
    return payload;
  },

  async getHistory(email) {
    const response = await fetch(`/api/ui/bookings?email=${encodeURIComponent(email)}`);
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.error || 'Unable to load history');
    }
    return payload.bookings || [];
  },
};

const state = {
  provider: '',
};

const slotContainer = document.querySelector('#slots-container');
const providerFilter = document.querySelector('#provider-filter');
const slotSelect = document.querySelector('#slot-select');
const form = document.querySelector('#booking-form');
const formMessage = document.querySelector('#form-message');
const confirmationPanel = document.querySelector('#confirmation-panel');
const historyForm = document.querySelector('#history-form');
const historyResults = document.querySelector('#history-results');

function formatDate(dateText) {
  const date = new Date(dateText);
  return new Intl.DateTimeFormat('en-US', { dateStyle: 'medium' }).format(date);
}

function formatTime(dateText) {
  const date = new Date(dateText);
  return new Intl.DateTimeFormat('en-US', { timeStyle: 'short' }).format(date);
}

function showMessage(text, type = 'success') {
  formMessage.textContent = text;
  formMessage.className = `message ${type}`;
}

function clearConfirmation() {
  confirmationPanel.hidden = true;
}

function buildEmptyState(messageText) {
  const item = document.createElement('div');
  item.className = 'history-item';
  item.textContent = messageText;
  return item;
}

function renderSlots(slots) {
  slotContainer.replaceChildren();
  slotSelect.replaceChildren();

  const defaultOption = document.createElement('option');
  defaultOption.value = '';
  defaultOption.textContent = 'Select a slot';
  slotSelect.appendChild(defaultOption);

  const providers = new Set();

  for (const slot of slots) {
    providers.add(slot.provider);
    const card = document.createElement('article');
    card.className = `slot-card ${slot.available ? 'available' : 'unavailable'}`;

    const slotTop = document.createElement('div');
    slotTop.className = 'slot-top';

    const badge = document.createElement('span');
    badge.className = `badge ${slot.available ? 'available' : 'unavailable'}`;
    badge.textContent = slot.available ? 'Available' : 'Booked';
    slotTop.appendChild(badge);

    const title = document.createElement('h3');
    title.textContent = slot.provider;

    const dateText = document.createElement('p');
    dateText.textContent = formatDate(slot.start);

    const timeText = document.createElement('p');
    timeText.textContent = `${formatTime(slot.start)} - ${formatTime(slot.end)}`;

    card.append(slotTop, title, dateText, timeText);

    if (slot.available) {
      const button = document.createElement('button');
      button.type = 'button';
      button.textContent = 'Select slot';
      button.addEventListener('click', () => {
        slotSelect.value = slot.id;
      });
      card.appendChild(button);
    }

    slotContainer.appendChild(card);

    const option = document.createElement('option');
    option.value = slot.id;
    option.dataset.provider = slot.provider;
    option.dataset.start = slot.start;
    option.dataset.end = slot.end;
    option.textContent = `${slot.provider} — ${formatDate(slot.start)} ${formatTime(slot.start)}`;
    option.disabled = !slot.available;
    slotSelect.appendChild(option);
  }

  providerFilter.replaceChildren();
  const allProvidersOption = document.createElement('option');
  allProvidersOption.value = '';
  allProvidersOption.textContent = 'All providers';
  providerFilter.appendChild(allProvidersOption);

  for (const provider of [...providers].sort()) {
    const option = document.createElement('option');
    option.value = provider;
    option.textContent = provider;
    providerFilter.appendChild(option);
  }

  if (state.provider) {
    providerFilter.value = state.provider;
  }

  const firstAvailable = slots.find((slot) => slot.available);
  const nextSlotLabel = document.querySelector('#next-slot');
  nextSlotLabel.textContent = firstAvailable ? `${firstAvailable.provider} • ${formatDate(firstAvailable.start)}` : 'No slots';
}

async function refreshSlots() {
  try {
    const slots = await api.getSlots(state.provider);
    renderSlots(slots);
  } catch (error) {
    showMessage(error.message, 'error');
  }
}

providerFilter.addEventListener('change', (event) => {
  state.provider = event.target.value;
  refreshSlots();
});

form.addEventListener('submit', async (event) => {
  event.preventDefault();
  const submitBtn = document.querySelector('#submit-btn');
  submitBtn.disabled = true;
  submitBtn.textContent = 'Booking…';
  clearConfirmation();
  showMessage('', 'success');

  try {
    const payload = {
      slot_id: document.querySelector('#slot-select').value,
      name: document.querySelector('#patient-name').value.trim(),
      email: document.querySelector('#patient-email').value.trim(),
    };
    const booking = await api.createBooking(payload);
    const selectedSlot = document.querySelector('#slot-select').selectedOptions[0];
    const slotStart = selectedSlot?.dataset.start ? new Date(selectedSlot.dataset.start) : null;
    const slotEnd = selectedSlot?.dataset.end ? new Date(selectedSlot.dataset.end) : null;

    showMessage('Booking confirmed successfully.', 'success');
    document.querySelector('#booking-id').textContent = booking.id;
    document.querySelector('#booking-name').textContent = booking.name;
    document.querySelector('#booking-provider').textContent = selectedSlot?.dataset.provider || 'Unknown provider';
    document.querySelector('#booking-date').textContent = slotStart ? formatDate(slotStart.toISOString()) : '—';
    document.querySelector('#booking-time').textContent = slotStart && slotEnd ? `${formatTime(slotStart.toISOString())} - ${formatTime(slotEnd.toISOString())}` : '—';
    document.querySelector('#booking-status').textContent = booking.status;
    confirmationPanel.hidden = false;
    form.reset();
    await refreshSlots();
  } catch (error) {
    showMessage(error.message, 'error');
  } finally {
    submitBtn.disabled = false;
    submitBtn.textContent = 'Confirm booking';
  }
});

historyForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  const email = document.querySelector('#history-email').value.trim();
  if (!email) return;

  try {
    const bookings = await api.getHistory(email);
    historyResults.replaceChildren();

    if (!bookings.length) {
      historyResults.appendChild(buildEmptyState('No bookings found for this email.'));
      return;
    }

    for (const booking of bookings) {
      const item = document.createElement('div');
      item.className = 'history-item';

      const title = document.createElement('strong');
      title.textContent = `${booking.name} — ${booking.status}`;
      item.appendChild(title);

      const dateLine = document.createElement('div');
      const historyDate = booking.start || booking.created_at;
      dateLine.textContent = historyDate ? `${formatDate(historyDate)} at ${formatTime(historyDate)}` : 'Appointment date unavailable';
      item.appendChild(dateLine);

      const providerLine = document.createElement('div');
      providerLine.textContent = `Provider: ${booking.provider || booking.slot_id}`;
      item.appendChild(providerLine);

      historyResults.appendChild(item);
    }
  } catch (error) {
    const message = document.createElement('div');
    message.className = 'history-item';
    message.textContent = error.message;
    historyResults.replaceChildren(message);
  }
});

refreshSlots();
