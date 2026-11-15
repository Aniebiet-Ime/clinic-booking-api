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

function renderSlots(slots) {
  slotContainer.innerHTML = '';
  slotSelect.innerHTML = '<option value="">Select a slot</option>';
  const providers = new Set();

  for (const slot of slots) {
    providers.add(slot.provider);
    const card = document.createElement('article');
    card.className = `slot-card ${slot.available ? 'available' : 'unavailable'}`;
    card.innerHTML = `
      <div class="slot-top">
        <span class="badge ${slot.available ? 'available' : 'unavailable'}">${slot.available ? 'Available' : 'Booked'}</span>
      </div>
      <h3>${slot.provider}</h3>
      <p>${formatDate(slot.start)}</p>
      <p>${formatTime(slot.start)} - ${formatTime(slot.end)}</p>
    `;

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
    option.textContent = `${slot.provider} — ${formatDate(slot.start)} ${formatTime(slot.start)}`;
    option.disabled = !slot.available;
    slotSelect.appendChild(option);
  }

  providerFilter.innerHTML = '<option value="">All providers</option>';
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
    showMessage('Booking confirmed successfully.', 'success');
    document.querySelector('#booking-id').textContent = booking.id;
    document.querySelector('#booking-name').textContent = booking.name;
    const provider = document.querySelector('#slot-select').selectedOptions[0]?.textContent || 'Provider';
    document.querySelector('#booking-provider').textContent = provider.split('—')[0].trim();
    document.querySelector('#booking-date').textContent = formatDate(booking.created_at);
    document.querySelector('#booking-time').textContent = formatTime(booking.created_at);
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
    historyResults.innerHTML = '';
    if (!bookings.length) {
      historyResults.innerHTML = '<div class="history-item">No bookings found for this email.</div>';
      return;
    }

    for (const booking of bookings) {
      const item = document.createElement('div');
      item.className = 'history-item';
      item.innerHTML = `
        <strong>${booking.name} — ${booking.status}</strong>
        <div>${formatDate(booking.created_at)} at ${formatTime(booking.created_at)}</div>
        <div>Provider: ${booking.slot_id}</div>
      `;
      historyResults.appendChild(item);
    }
  } catch (error) {
    historyResults.innerHTML = `<div class="history-item">${error.message}</div>`;
  }
});

refreshSlots();
