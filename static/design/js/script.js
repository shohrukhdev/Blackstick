/**
 * Booket — Client Booking Script
 *
 * Booking flow (3 modal steps):
 *   1. #book       — Select services offered by the chosen specialist
 *   2. #date-time  — Pick an available date and time slot
 *   3. #confirm    — Enter client details, submit → receive OTP → verify
 *
 * Entry point: selectServer(providerServerId, serverName)
 *   Called by the "Book appointment" button on each specialist card.
 *   Note: providerServerId is the ProviderServer.id (not Server.id).
 *
 * API endpoints used:
 *   GET  /provider-server/<p_server_id>/              → services + initial slots
 *   GET  /provider-server/<p_server_id>/available-slots/?start_date=YYYY-MM-DD
 *   GET  /client/search/?phone_number=... | ?email=...
 *   POST /client/appointment/create/                  → create appointment + send OTP
 *   POST /client/appointment/confirm/                 → verify OTP
 *   POST /client/appointment/confirm/resend/          → resend OTP
 */

// ─── i18n ──────────────────────────────────────────────────────────────────────

const MESSAGES = {
    en: {
        noSlots: "No available time slots",
        slotUnavailable: "This time slot is not available for the selected services",
        genericError: "An error occurred while processing your request.",
        unknownError: "Unknown error occurred",
        invalidOtp: "Invalid OTP code",
        resendFailed: "Failed to resend code"
    },
    ru: {
        noSlots: "Нет доступных временных слотов",
        slotUnavailable: "Этот интервал недоступен для выбранных услуг",
        genericError: "Произошла ошибка при обработке вашего запроса.",
        unknownError: "Произошла неизвестная ошибка",
        invalidOtp: "Неверный код подтверждения",
        resendFailed: "Не удалось отправить код повторно"
    },
    uz: {
        noSlots: "Mavjud vaqt oralig'i yo'q",
        slotUnavailable: "Tanlangan xizmatlar uchun bu vaqt oralig'i mavjud emas",
        genericError: "So'rovingizni bajarishda xatolik yuz berdi.",
        unknownError: "Noma'lum xatolik yuz berdi",
        invalidOtp: "Noto'g'ri tasdiqlash kodi",
        resendFailed: "Kod qayta yuborilmadi"
    }
};

function getLang() {
    const val = $('#cur_lang').val();
    return val ? String(val).toLowerCase() : 'en';
}

function t(key) {
    const lang = getLang();
    return (MESSAGES[lang] && MESSAGES[lang][key]) || (MESSAGES.en && MESSAGES.en[key]) || key;
}

// ─── Globals ───────────────────────────────────────────────────────────────────

/** Booking state accumulated across all three modal steps. */
const appointment = { services: [] };

const signature = $("#signature").val();

/** Last API response from ProviderServerDetailView — holds service types and slot data. */
let responseData = {};

/** First and last visible date in the date-picker (used for pagination). */
let firstDate;
let lastDate;

let timerInterval = null;

// ─── Initialization ────────────────────────────────────────────────────────────

$(document).ready(function () {
    initializeModals();
    initializeComponents();
    setupEventListeners();
});

function initializeModals() {
    $("#book").modal({ backdrop: 'static', keyboard: false, show: false });
    $("#date-time").modal({ backdrop: 'static', keyboard: false, show: false });
    $("#confirm").modal({ backdrop: 'static', keyboard: false, show: false });
}

function initializeComponents() {
    $('[data-toggle="popover"]').popover({ trigger: 'click', placement: 'auto' });
    flatpickr('.date-picker', {
        dateFormat: "d.m.Y",
        allowInput: false,
        disableMobile: true
    });
    appointment.provider_identifier = $("#provider_identifier").val();
}

function setupEventListeners() {
    // Language switcher
    $("#langToggle").on("click", toggleLanguageDropdown);
    $(".lang-option").on("click", handleLanguageChange);

    // Service accordion on the main page (not inside modals)
    $(".service_box .header").on("click", toggleServiceAccordion);

    // Service checkboxes inside the #book modal (delegated — rendered dynamically)
    $(document).on('change', '.service-checkbox', handleServiceCheckboxChange);

    // Date-time modal: reset slots when modal closes
    $("#date-time").on("hidden.bs.modal", resetTimeSlots);

    // Date navigation buttons
    $("#prevDateBtn").on("click", function () { getDates("previous"); });
    $("#nextDateBtn").on("click", function () { getDates("next"); });

    // Phone / email inputs in the confirm modal
    $('#phone').on('input', checkPhoneInput);
    $('#email').on('input', checkEmailInput);

    // Confirm form field changes — re-check whether submit button should be enabled
    $(document).on('input change', '#full_name, #dob, #sex, #agree', checkConfirmButton);

    // OTP input — enable confirm button when 6 digits are entered
    $(document).on('input', '#otp_code', updateOTPConfirmButton);
}

// ─── Language ──────────────────────────────────────────────────────────────────

function toggleLanguageDropdown() {
    $("#langDropdown").toggleClass("show");
}

function handleLanguageChange() {
    const lang = $(this).data("lang").toLowerCase();
    const flag = $(this).data("flag");
    $("#currentLang").text(lang);
    $("#currentFlag").attr("src", flag);
    $("#langDropdown").removeClass("show");
    $("#cur_lang").val(lang);
    $("#setlangform").submit();
}

// ─── Step 1: Service Selection ─────────────────────────────────────────────────

/**
 * Open the booking flow for a given specialist.
 * Fetches the specialist's services and initial time slots, then opens #book modal.
 *
 * @param {string|number} providerServerId  - ProviderServer.id (NOT Server.id)
 * @param {string}        serverName        - Display name shown in modal header
 */
function selectServer(providerServerId, serverName) {
    appointment.services = [];
    appointment.server_id = providerServerId;

    $('#goToDateSelectBtn').prop('disabled', true);
    $("#bookLabel, #date-timeLabel, #confirmLabel").text(serverName);

    $.ajax({
        url: `/provider-server/${providerServerId}/`,
        type: "GET",
        dataType: "json",
        headers: { 'X-CSRFToken': getCookie('csrftoken'), 'X-Signature': signature },
        success: function (response) {
            responseData = response;
            appointment.server_name = serverName;
            fillServices(response.service_types, getLang());
            $("#book").modal("show");
        },
        error: handleAjaxError
    });
}

/**
 * Render the service-selection list inside the #book modal.
 *
 * @param {Array}  serviceTypes  - Array of service type objects from the API
 * @param {string} langCode      - Active language code ('en', 'ru', 'uz')
 */
function fillServices(serviceTypes, langCode) {
    $('#ps_services').empty();

    $.each(serviceTypes, function (_, serviceType) {
        const typeName = langCode === "uz" ? serviceType.name_uz
            : langCode === "ru" ? serviceType.name_ru
            : serviceType.name;

        let html = `
            <div class="service_box">
              <div class="header">
                <h1>${typeName}</h1>
                <div class="icon-arrow"><img src="/static/design/images/arrow-up.svg" alt="icon"></div>
              </div>
              <div class="list">
                <ul class="list-group list-group-flush">`;

        $.each(serviceType.services, function (_, service) {
            const price = service.service_private_price !== null ? service.service_private_price : service.price;
            const name = langCode === "uz" ? service.name_uz
                : langCode === "ru" ? service.name_ru
                : service.name;

            html += `
                <li class="list-group-item service-list-item">
                  <div class="d-flex align-items-center justify-content-between w-100">
                    <div class="service-text-container">
                      <p class="service-name">${name}</p>
                      <small class="service-price d-block">&gt; ${Number(price).toLocaleString()}</small>
                    </div>
                    <div class="checkbox-container">
                      <input class="form-check-input position-static service-checkbox"
                        type="checkbox"
                        id="service_cb_${service.id}"
                        data-id="${service.id}"
                        data-name="${name}"
                        data-price="${price}"
                        data-duration="${service.duration}"
                        aria-label="${name}">
                    </div>
                  </div>
                </li>`;
        });

        html += `</ul></div></div>`;
        $('#ps_services').append(html);
    });

    // Re-apply accordion listener to newly rendered headers
    $('#ps_services').find('.header').on('click', toggleServiceAccordion);
}

/**
 * Handle a service checkbox being checked or unchecked.
 * Updates appointment.services and recalculates total duration.
 */
function handleServiceCheckboxChange() {
    const serviceId = $(this).data('id');
    const price = $(this).data('price');
    const duration = $(this).data('duration');
    const serviceName = $(this).data('name');

    if ($(this).is(':checked')) {
        appointment.services.push({ service_id: serviceId, service_name: serviceName, price: price, duration: duration });
    } else {
        appointment.services = appointment.services.filter(s => s.service_id !== serviceId);
    }

    $('#goToDateSelectBtn').prop('disabled', appointment.services.length === 0);
    updateTotalDuration();
}

function updateTotalDuration() {
    $("#duration").text(calculateTotalDuration(appointment.services));
}

// ─── Step 2: Date & Time Selection ────────────────────────────────────────────

/**
 * Navigate to the date/time step.
 * Re-uses already-loaded slot data from responseData to avoid a redundant request.
 */
function goToDateTimeSelect() {
    updateTotalDuration();
    renderDates(responseData.available_time_slots);
    $("#book").modal("hide");
    $("#date-time").modal("show");
}

/**
 * Fetch available dates from the API and re-render the date picker.
 *
 * @param {'next'|'previous'} direction
 */
function getDates(direction) {
    const startParam = direction === "next"
        ? modifyDate(lastDate, 1)
        : modifyDate(firstDate || new Date().toISOString().split('T')[0], -3);

    const endpoint = `/provider-server/${responseData.id}/available-slots/?start_date=${startParam}`;

    $.ajax({
        url: endpoint,
        type: "GET",
        dataType: "json",
        headers: { 'X-CSRFToken': getCookie('csrftoken'), 'X-Signature': signature },
        success: function (response) {
            renderDates(response.available_slots);
        },
        error: handleAjaxError
    });
}

/**
 * Render date buttons in the date picker.
 *
 * @param {Array} availableSlots  - Array of {date, slots} objects from the API
 */
function renderDates(availableSlots) {
    $("#dateContainer").empty();
    $("#timeSlots").empty();
    const langCode = getLang();

    $.each(availableSlots, function (index, item) {
        const dateBtn = $("<button>")
            .addClass("btn btn-outline-secondary day-btn")
            .text(formatDate(item.date, "DD-MM"))
            .on("click", function () {
                $("#dateContainer button").removeClass("btn-primary active");
                $(this).addClass("btn-primary active");
                appointment.date = item.date;
                updateSelectedDateText(item.date, langCode);
                renderTimeSlots(item.slots);
            });

        if (index === 0) {
            firstDate = item.date;
            dateBtn.addClass("btn-primary active");
            appointment.date = item.date;
            updateSelectedDateText(item.date, langCode);
            renderTimeSlots(item.slots);
        }
        lastDate = item.date;
        $("#dateContainer").append(dateBtn);
    });
}

/**
 * Render available time slot buttons for the selected date.
 * Validates that a slot has enough consecutive availability for all selected services.
 *
 * @param {string[]} slots  - Array of "HH:MM" time strings
 */
function renderTimeSlots(slots) {
    $("#timeSlots").empty();
    $("#goToConfirmBtn").prop("disabled", true);
    appointment.time = undefined;

    if (!Array.isArray(slots) || slots.length === 0) {
        $("#timeSlots").append($("<div>").addClass("no-slots").text(t('noSlots')));
        return;
    }

    $.each(slots, function (_, time) {
        const timeDiv = $("<div>")
            .addClass("time-slot")
            .attr("data-time", time)
            .text(time)
            .on("click", function () {
                $("#timeSlots .time-slot").removeClass("selected");
                const totalDuration = calculateTotalDuration(appointment.services);
                if (isSlotAvailable(time, totalDuration, slots)) {
                    $(this).addClass("selected");
                    appointment.time = time;
                    $("#goToConfirmBtn").prop("disabled", false);
                } else {
                    $("#goToConfirmBtn").prop("disabled", true);
                    showError(t('slotUnavailable'));
                }
            });

        $("#timeSlots").append(timeDiv);
    });
}

/**
 * Check whether a given start time has enough consecutive 30-min slots
 * to cover the total service duration.
 *
 * @param {string}   selectedTime   - "HH:MM"
 * @param {number}   totalDuration  - Total minutes needed
 * @param {string[]} availableSlots - All available "HH:MM" slots for the day
 * @returns {boolean}
 */
function isSlotAvailable(selectedTime, totalDuration, availableSlots) {
    const [startHour, startMin] = selectedTime.split(':').map(Number);
    const startMinutes = startHour * 60 + startMin;
    const endMinutes = startMinutes + totalDuration;
    const requiredSlots = [];

    for (let m = startMinutes; m < endMinutes; m += 30) {
        const h = String(Math.floor(m / 60)).padStart(2, '0');
        const min = String(m % 60).padStart(2, '0');
        requiredSlots.push(`${h}:${min}`);
    }

    return requiredSlots.every(slot => availableSlots.includes(slot));
}

/**
 * Return a date string offset by the given number of days.
 *
 * @param {string} dateStr  - "YYYY-MM-DD"
 * @param {number} days     - Positive = future, negative = past
 * @returns {string}        - "YYYY-MM-DD"
 */
function modifyDate(dateStr, days) {
    const date = new Date(dateStr);
    date.setDate(date.getDate() + days);
    return date.toISOString().split('T')[0];
}

/**
 * Update the "30 JAN, Monday" label above the time slot grid.
 *
 * @param {string} dateStr   - "YYYY-MM-DD"
 * @param {string} langCode  - 'en', 'ru', or 'uz'
 */
function updateSelectedDateText(dateStr, langCode) {
    const date = new Date(dateStr);
    const day = date.getDate();
    const monthIndex = date.getMonth();
    const weekdayIndex = date.getDay();

    const months = {
        en: ['JAN','FEB','MAR','APR','MAY','JUN','JUL','AUG','SEP','OCT','NOV','DEC'],
        ru: ['ЯНВ','ФЕВ','МАР','АПР','МАЙ','ИЮНЬ','ИЮЛЬ','АВГ','СЕН','ОКТ','НОЯ','ДЕК'],
        uz: ['YAN','FEV','MAR','APR','MAY','IYUN','IYUL','AVG','SEN','OKT','NOY','DEK']
    };
    const weekdays = {
        en: ['Sunday','Monday','Tuesday','Wednesday','Thursday','Friday','Saturday'],
        ru: ['Воскресенье','Понедельник','Вторник','Среда','Четверг','Пятница','Суббота'],
        uz: ['Yakshanba','Dushanba','Seshanba','Chorshanba','Payshanba','Juma','Shanba']
    };

    const lang = months[langCode] ? langCode : 'en';
    $('#selectedDateText').text(`${day} ${months[lang][monthIndex]}, ${weekdays[lang][weekdayIndex]}`);
}

function resetTimeSlots() {
    $("#timeSlots").empty();
    $(".time-slot").removeClass("selected");
}

// ─── Step 3: Confirmation & OTP ────────────────────────────────────────────────

/**
 * Navigate to the confirmation step.
 * Populates the appointment summary on the left side of the modal.
 */
function goToConfirm() {
    renderConfirm();
    $("#date-time").modal("hide");
    $("#confirm").modal("show");
}

/**
 * Populate the appointment summary panel in the #confirm modal
 * (time, date, service list, total duration, total amount).
 */
function renderConfirm() {
    try {
        if (appointment.time) $("#appointment_time").text(appointment.time);
        if (appointment.date) $("#appointment_date").text(formatDate(appointment.date, 'DD.MM.YYYY'));

        const $list = $("#appointment_services").empty();
        appointment.services.forEach(svc => {
            const $li = $(`
                <li>
                  <p></p>
                  <div class="d-flex align-items-center justify-content-end" style="gap: 10px;">
                    <span></span>
                    <div class="time">
                      <img src="/static/design/images/clock-grey.svg" alt="icon">
                      <p></p>
                    </div>
                  </div>
                </li>`);
            $li.find('p').first().text(svc.service_name || '');
            $li.find('span').text(Number(svc.price).toLocaleString());
            $li.find('.time p').text(`${svc.duration} min`);
            $list.append($li);
        });

        $("#appointment_duration").text(calculateTotalDuration(appointment.services));
        $("#appointment_total").text(Number(calculateTotalSum(appointment.services)).toLocaleString());
    } catch (e) {
        console.error('Error rendering confirm modal:', e);
    }
}

function selectConfirmByPhone() {
    $("#confirm_by_email").removeClass("active");
    $("#confirm_by_phone").addClass("active");
    clearConfirmFields();
    $("#phone_field").show();
    $("#email_field").hide();
}

function selectConfirmByEmail() {
    $("#confirm_by_phone").removeClass("active");
    $("#confirm_by_email").addClass("active");
    clearConfirmFields();
    $("#phone_field").hide();
    $("#email_field").show();
    $("#enter_text").hide();
    $("#clientFound").hide();
}

function clearConfirmFields() {
    $("#full_name, #dob, #phone, #email").val("");
    $("#sex").val("m");
    $("#client_id").val("");
}

/**
 * Called on phone input — triggers client lookup when 9 digits are entered.
 */
function checkPhoneInput() {
    const phone = $(this).val();
    if (phone.length > 8) {
        searchClient({ phone_number: `+998${phone}` });
    } else {
        $('#client_form_field').hide();
        checkConfirmButton();
    }
}

/**
 * Called on email input — triggers client lookup when a valid email is entered.
 */
function checkEmailInput() {
    const email = $(this).val();
    if (isValidEmail(email)) {
        searchClient({ email });
    } else {
        $('#client_form_field').hide();
        checkConfirmButton();
    }
}

function isValidEmail(email) {
    return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
}

/**
 * Look up an existing client by phone or email.
 * On success, pre-fills the client form fields.
 * On 404, shows an empty form for the user to fill in.
 *
 * @param {{ phone_number?: string, email?: string }} searchData
 */
function searchClient(searchData) {
    $.ajax({
        url: '/client/search/',
        type: 'GET',
        data: searchData,
        headers: { 'X-CSRFToken': getCookie('csrftoken'), 'X-Signature': signature },
        success: function (response) {
            if (response.success) {
                $('#full_name').val(response.client_full_name);
                $('#dob').val(response.client_dob);
                $('#sex').val(response.client_sex);
                $('#client_id').val(response.client_id);
                $('#enter_text').hide();
                $('#clientFound').show();
                $('#client_form_field').show();
                checkConfirmButton();
            }
        },
        error: function () {
            $('#full_name, #dob').val('');
            $('#sex').val('m');
            $('#client_id').val('');
            $('#clientFound').hide();
            $('#enter_text').show();
            $('#client_form_field').show();
            checkConfirmButton();
        }
    });
}

/**
 * Enable/disable the #confirmBtn based on whether all required form fields are filled.
 */
function checkConfirmButton() {
    const filled = $('#full_name').val() && $('#dob').val() && $('#sex').val() && $('#agree').is(':checked');
    $('#confirmBtn').prop('disabled', !filled);
}

/**
 * Build the appointment payload and POST to the create-appointment endpoint.
 * On success, stores the returned otp_id and shows the OTP input.
 */
function sendToConfirm() {
    const isPhoneMethod = $("#confirm_by_phone").hasClass("active");
    const dobFormatted = parseDob($("#dob").val());

    const payload = {
        client: {
            client_id: $("#client_id").val() || null,
            full_name: $("#full_name").val(),
            phone_number: isPhoneMethod ? `+998${$("#phone").val()}` : null,
            email: isPhoneMethod ? null : $("#email").val(),
            sex: $("#sex").val(),
            dob: dobFormatted,
            confirmation_method: isPhoneMethod ? 'p' : 'e'
        },
        provider_id: $("#provider_id").val(),
        server_id: appointment.server_id,
        date: appointment.date,
        time: appointment.time,
        services: appointment.services.map(s => ({
            service_id: s.service_id,
            duration: s.duration
        })),
        comments: $("#comments").val(),
        language_code: getLang()
    };

    $("#confirmBtn").prop('disabled', true);

    $.ajax({
        url: '/client/appointment/create/',
        method: 'POST',
        contentType: 'application/json',
        data: JSON.stringify(payload),
        headers: { 'X-CSRFToken': getCookie('csrftoken'), 'X-Signature': signature },
        success: handleAppointmentCreationSuccess,
        error: function (error) {
            $("#confirmBtn").prop('disabled', false);
            handleAjaxError(error);
        }
    });
}

// ─── OTP Verification ──────────────────────────────────────────────────────────

/**
 * Handle a successful response from the create-appointment endpoint.
 * Stores the OTP ID and transitions the modal to OTP input.
 *
 * @param {Object} response  - API response body
 */
function handleAppointmentCreationSuccess(response) {
    if (response.success) {
        appointment.otp_id = response.otp_id;
        showOTPConfirmation(response);
    } else {
        $("#confirmBtn").prop('disabled', false);
        showError(response.message || t('unknownError'));
    }
}

/**
 * Transition the #confirm modal's right panel from the client form to the OTP section.
 *
 * @param {Object} response  - API response (contains confirmation_method, masked contact, otp_id)
 */
function showOTPConfirmation(response) {
    const destination = response.confirmation_method === 'p'
        ? response.masked_phone_number
        : response.masked_email;

    $("#clientConfirmationForm").hide();
    $("#confirmBackBtn").hide();
    $("#confirmBtn").hide();

    if (response.is_demo && response.otp_code) {
        $("#demo_otp_code").text(response.otp_code);
        $("#demo_otp_banner").show();
    }

    $("#confirmation_destination").text(destination || '');
    $("#confirmationCodeSection").show();
    startOTPTimer();
}

/**
 * Start the 60-second countdown before the Resend button becomes available.
 */
function startOTPTimer() {
    let timeLeft = 60;
    $("#timer").text(timeLeft);
    $("#resendBtn").prop("disabled", true).hide();
    $("#resend_timer").show();

    clearInterval(timerInterval);
    timerInterval = setInterval(function () {
        timeLeft--;
        $("#timer").text(timeLeft);
        if (timeLeft <= 0) {
            clearInterval(timerInterval);
            $("#resend_timer").hide();
            $("#resendBtn").prop("disabled", false).show();
        }
    }, 1000);
}

function updateOTPConfirmButton() {
    $("#otpConfirmBtn").prop("disabled", $("#otp_code").val().length < 6);
}

/**
 * Submit the entered OTP code for verification.
 */
function confirmOTP() {
    const otpCode = $("#otp_code").val();

    $.ajax({
        url: '/client/appointment/confirm/',
        method: 'POST',
        contentType: 'application/json',
        data: JSON.stringify({
            otp_id: appointment.otp_id,
            otp_code: otpCode,
            provider_identifier: appointment.provider_identifier
        }),
        headers: { 'X-CSRFToken': getCookie('csrftoken'), 'X-Signature': signature },
        success: function (response) {
            if (response.success) {
                showSuccessMessage(response);
            } else {
                showError(response.message || t('invalidOtp'));
            }
        },
        error: handleAjaxError
    });
}

/**
 * Request a new OTP code to be sent to the client's contact.
 */
function resendOTP() {
    $.ajax({
        url: '/client/appointment/confirm/resend/',
        method: 'POST',
        contentType: 'application/json',
        data: JSON.stringify({ otp_id: appointment.otp_id }),
        headers: { 'X-CSRFToken': getCookie('csrftoken'), 'X-Signature': signature },
        success: function (response) {
            if (response.success) {
                $("#otp_code").val('');
                $("#otpConfirmBtn").prop("disabled", true);
                startOTPTimer();
            } else {
                showError(response.message || t('resendFailed'));
            }
        },
        error: handleAjaxError
    });
}

/**
 * Show the success message after the appointment is confirmed via OTP.
 * Displays the appointment ID and a status description.
 *
 * @param {Object} response  - API response from /client/appointment/confirm/
 */
function showSuccessMessage(response) {
    clearInterval(timerInterval);
    $("#confirmationCodeSection").hide();

    const appointmentId = response.appointment_id;
    const appointmentStatus = response.appointment_status;

    $("#successAppointmentId").text(`№${appointmentId}`);

    const statusDescriptions = {
        ACCEPTED: {
            en: "Your appointment is confirmed and accepted. See you soon!",
            ru: "Ваша запись подтверждена и принята. До встречи!",
            uz: "Uchrashuv tasdiqlandi va qabul qilindi. Ko'rishguncha!"
        },
        CONFIRMED: {
            en: "Your appointment is confirmed. The specialist will review it shortly.",
            ru: "Ваша запись подтверждена. Специалист рассмотрит её в ближайшее время.",
            uz: "Uchrashuv tasdiqlandi. Mutaxassis yaqinda ko'rib chiqadi."
        }
    };

    const lang = getLang();
    const desc = (statusDescriptions[appointmentStatus] || statusDescriptions.CONFIRMED)[lang]
        || statusDescriptions.CONFIRMED.en;
    $("#successStatusDescription").text(desc);

    $(".confirmationSuccess").show();
}

// ─── Modal Navigation ──────────────────────────────────────────────────────────

/**
 * Go back from Step 2 (date/time) to Step 1 (service selection).
 */
function goBackToServiceSelect() {
    $("#date-time").modal("hide");
    $('#goToDateSelectBtn').prop('disabled', appointment.services.length === 0);
    $("#book").modal("show");
}

/**
 * Go back from Step 3 (confirm) to Step 2 (date/time).
 */
function goBackToDateTime() {
    $("#confirm").modal("hide");
    $("#date-time").modal("show");
}

/**
 * Close all booking modals and reset all booking state.
 */
function closeModal() {
    clearInterval(timerInterval);
    $('#book, #date-time, #confirm').modal("hide");
    resetAppointmentData();
    resetConfirmModal();
}

function resetAppointmentData() {
    appointment.services = [];
    appointment.date = undefined;
    appointment.time = undefined;
    appointment.otp_id = undefined;
    responseData = {};
    firstDate = undefined;
    lastDate = undefined;
}

function resetConfirmModal() {
    $("#clientConfirmationForm").show();
    $("#confirmationCodeSection, #demo_otp_banner, .confirmationSuccess").hide();
    $("#confirmBackBtn, #confirmBtn").show();
    $("#confirmBtn").prop('disabled', true);
    $("#otp_code").val('');
    selectConfirmByPhone();
    $("#client_form_field").hide();
}

// ─── Utilities ─────────────────────────────────────────────────────────────────

function calculateTotalDuration(services) {
    return services.reduce((sum, s) => sum + Number(s.duration), 0);
}

function calculateTotalSum(services) {
    return services.reduce((sum, s) => sum + Number(s.price), 0);
}

/**
 * Format a date string or Date object.
 *
 * @param {string|Date} date
 * @param {'YYYY-MM-DD'|'DD-MM'|'DD.MM.YYYY'} format
 * @returns {string}
 */
function formatDate(date, format) {
    const d = new Date(date);
    const year = d.getFullYear();
    const month = String(d.getMonth() + 1).padStart(2, '0');
    const day = String(d.getDate()).padStart(2, '0');
    if (format === 'DD-MM')       return `${day}-${month}`;
    if (format === 'DD.MM.YYYY')  return `${day}.${month}.${year}`;
    return `${year}-${month}-${day}`;
}

/**
 * Convert a user-visible date string to YYYY-MM-DD for the API.
 * Handles both flatpickr output (d.m.Y) and ISO format (from API auto-fill).
 *
 * @param {string} dobStr  - "31.01.1990" or "1990-01-31"
 * @returns {string|null}  - "YYYY-MM-DD" or null
 */
function parseDob(dobStr) {
    if (!dobStr) return null;
    if (/^\d{4}-\d{2}-\d{2}$/.test(dobStr)) return dobStr;
    if (/^\d{1,2}\.\d{1,2}\.\d{4}$/.test(dobStr)) {
        const [d, m, y] = dobStr.split('.');
        return `${y}-${m.padStart(2, '0')}-${d.padStart(2, '0')}`;
    }
    return dobStr;
}

function toggleServiceAccordion() {
    const $list = $(this).next(".list");
    const $icon = $(this).find(".icon-arrow");
    if ($list.is(":visible")) {
        $list.slideUp(300);
        $icon.css("transform", "rotate(0deg)");
    } else {
        $list.slideDown(300);
        $icon.css("transform", "rotate(180deg)");
    }
}

/**
 * Get a cookie value by name (used to retrieve the CSRF token).
 *
 * @param {string} name
 * @returns {string|null}
 */
function getCookie(name) {
    if (!document.cookie) return null;
    const match = document.cookie.split(';')
        .map(c => c.trim())
        .find(c => c.startsWith(name + '='));
    return match ? decodeURIComponent(match.split('=')[1]) : null;
}

/**
 * Generic AJAX error handler. Extracts a human-readable message and shows it.
 *
 * @param {Object} error  - jQuery AJAX error object
 */
function handleAjaxError(error) {
    console.error("AJAX Error:", error);
    const message = (error.responseJSON && (error.responseJSON.error || error.responseJSON.message))
        || error.statusText
        || t('genericError');
    showError(message);
}

/**
 * Show a Bootstrap toast notification.
 * Self-contained so it works regardless of which base template is loaded.
 *
 * @param {string} message
 * @param {string} type  - 'success' | 'error' | 'warning' | 'info'
 */
function showToast(message, type) {
    type = type || 'info';
    var bgMap = {
        success: 'bg-success text-white',
        error: 'bg-danger text-white',
        danger: 'bg-danger text-white',
        warning: 'bg-warning text-dark',
        info: 'bg-primary text-white'
    };
    var cls = bgMap[type] || bgMap.info;

    var container = document.querySelector('.toast-container');
    if (!container) {
        container = document.createElement('div');
        container.className = 'toast-container position-fixed top-0 end-0 p-3';
        container.style.zIndex = '105000';
        document.body.appendChild(container);
    }

    // Remove previous toasts to avoid stacking
    container.innerHTML = '';

    var toastEl = document.createElement('div');
    toastEl.className = 'toast align-items-center ' + cls + ' border-0 shadow';
    toastEl.setAttribute('role', 'alert');
    toastEl.setAttribute('aria-live', 'assertive');
    toastEl.setAttribute('aria-atomic', 'true');
    toastEl.setAttribute('data-bs-autohide', 'true');
    toastEl.setAttribute('data-bs-delay', '8000');
    toastEl.innerHTML =
        '<div class="d-flex">' +
        '<div class="toast-body">' + message + '</div>' +
        '<button type="button" class="btn-close btn-close-white me-2 m-auto" ' +
        'data-bs-dismiss="toast" aria-label="Close"></button>' +
        '</div>';

    container.appendChild(toastEl);

    if (typeof bootstrap !== 'undefined' && bootstrap.Toast) {
        var toastInstance = new bootstrap.Toast(toastEl, { delay: 8000 });
        toastInstance.show();

        // Explicit close button handler (programmatic toasts need this wired manually)
        toastEl.querySelector('[data-bs-dismiss="toast"]').addEventListener('click', function () {
            toastInstance.hide();
        });

        // Dismiss on any link or button click outside the toast
        function dismissOnNav(e) {
            if (!toastEl.contains(e.target)) {
                toastInstance.hide();
            }
        }
        document.addEventListener('click', dismissOnNav);

        // Clean up the nav handler once toast is fully hidden
        toastEl.addEventListener('hidden.bs.toast', function () {
            document.removeEventListener('click', dismissOnNav);
        }, { once: true });
    }
}

/**
 * Display an error toast message to the user.
 *
 * @param {string} message
 */
function showError(message) {
    showToast(message, 'error');
}
