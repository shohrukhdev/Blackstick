$(document).ready(function () {
    setupEventListeners();
    $("#book").modal({backdrop: 'static', keyboard: false, show: false});
    $("#date-time").modal({backdrop: 'static', keyboard: false, show: false});
    $("#confirm").modal({backdrop: 'static', keyboard: false, show: false});

    // Event Delegation: Handle Service Checkbox Changes
    $(document).on('change', '.service-checkbox', handleServiceCheckboxChange);
    initializeComponents();

    // Add listeners for phone and email inputs
    $('#phone').on('input', checkPhoneInput);
    $('#email').on('input', checkEmailInput);
});

// Simple i18n messages map and helpers
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
    return (val ? String(val).toLowerCase() : 'en');
}
function t(key) {
    const lang = getLang();
    return (MESSAGES[lang] && MESSAGES[lang][key]) || (MESSAGES.en && MESSAGES.en[key]) || key;
}


// Global variables for managing appointment data
const appointment = {services: []};
const signature = $("#signature").val();
let responseData = {};
let lastDate;
let firstDate;
let timerInterval = null;

/**
 * Initialize all components and plugins
 */
function initializeComponents() {
    // Initialize popovers
    $('[data-toggle="popover"]').popover({
        trigger: 'click',
        placement: 'auto'
    });

    // Initialize date pickers
    initializeDatePickers();

    // Set provider identifier
    appointment.provider_identifier = $("#provider_identifier").val() || $('meta[name="provider-identifier"]').attr('content');
}

/**
 * Initialize date pickers with flatpickr
 */
function initializeDatePickers() {
    flatpickr('.date-picker', {
        dateFormat: "d.m.Y",
        allowInput: false,
        disableMobile: true
    });
}

/**
 * Setup all event listeners
 */
function setupEventListeners() {
    // Language toggle
    $("#langToggle").on("click", toggleLanguageDropdown);
    $(".lang-option").on("click", handleLanguageChange);

    // Service accordion
    $(".service_box .header").on("click", toggleServiceAccordion);

    // Modal events
    $("#date-time").on("hidden.bs.modal", function () {
        resetTimeSlots();
    });

    // Navigation buttons for dates
    $("#prevDateBtn").on("click", function () {
        getDates("previous");
    });
    $("#nextDateBtn").on("click", function () {
        getDates("next");
    });

    // Form tab handling
    $("#phone-number-tab, #email-tab").on("shown.bs.tab", handleConfirmationMethodChange);

    // Check agreement checkbox to enable confirm button
    $("#defaultCheck1, #defaultCheck2").on("change", function () {
        updateConfirmButton();
    });

    // OTP code input
    $("#otp_code").on("input", function () {
        updateOTPConfirmButton();
    });
}

/**
 * Toggle the language dropdown
 */
function toggleLanguageDropdown() {
    $("#langDropdown").toggleClass("show");
}

/**
 * Handle language selection and form submission
 */
function handleLanguageChange() {
    const lang = $(this).data("lang").toLowerCase();
    const flag = $(this).data("flag");

    $("#currentLang").text(lang);
    $("#currentFlag").attr("src", flag);
    $("#langDropdown").removeClass("show");

    // Set language value and submit form
    $("#cur_lang").val(lang);
    $("#setlangform").submit();
}

/**
 * Toggle service accordion open/close
 */
function toggleServiceAccordion() {
    const $header = $(this);
    const $list = $header.next(".list");
    const $icon = $header.find(".icon-arrow");

    if ($list.is(":visible")) {
        $list.slideUp(300);
        $icon.css("transform", "rotate(0deg)");
    } else {
        $list.slideDown(300);
        $icon.css("transform", "rotate(180deg)");
    }
}

/**
 * Select a server and initialize booking process
 * @param {string} serverId - The server ID
 * @param {string} serverName - The server name
 */
function selectServer(serverId, serverName) {
    appointment.services = [];
    appointment.server_id = serverId;
    $('#goToDateSelectBtn').attr("disabled", "disabled")
    // Update modal title with server name
    $("#bookLabel, #date-timeLabel, #confirmLabel").text(`${serverName}`);

    // Fetch server services
    const endpoint = `/provider-server/${serverId}/`;
    const lang_code = $('#cur_lang').val();
    $.ajax({
        url: endpoint,
        type: "GET",
        dataType: "json",
        headers: {'X-CSRFToken': getCookie('csrftoken'), 'X-Signature': signature},
        success: function (response) {
            responseData = response;
            appointment.server_id = serverId;
            appointment.server_name = serverName
            fillServices(response.service_types, lang_code);
            renderDates(response.available_time_slots);
            $("#book").modal("show");
        },
        error: function (error) {
            handleAjaxError(error)
        }
    });
}

    function fillServices(service_types, lang_code) {
        $('#ps_services').empty();
        $.each(service_types, function (index, service_type) {
            const serviceTypeName = lang_code === "uz" ? service_type.name_uz :
                lang_code === "ru" ? service_type.name_ru :
                    service_type.name;
            let serviceBox = `
                <div class="service_box">
                <div class="header">
                  <h1>${serviceTypeName}</h1>
                </div>
                <div class="list">
                <ul class="list-group list-group-flush">       
                `;

            $.each(service_type.services, function (index, service) {
                const price = service.service_private_price !== null ? service.service_private_price : service.price;
                const serviceName = lang_code === "uz" ? service.name_uz :
                    lang_code === "ru" ? service.name_ru :
                        service.name;

                serviceBox += `
                <li class="list-group-item service-list-item">
                  <div class="d-flex align-items-center justify-content-between w-100">
                    <div class="service-text-container">
                      <p class="service-name">${serviceName}</p>
                      <small class="service-price d-block">> ${price.toLocaleString()}</small>
                    </div>
                    <div class="checkbox-container">
                      <input class="form-check-input position-static service-checkbox" 
                        type="checkbox" 
                        id="blankCheckbox_${service.id}"
                        data-id="${service.id}"
                        data-name="${serviceName}"
                        data-price="${price}"
                        data-duration="${service.duration}" 
                        aria-label="...">
                    </div>
                  </div>
                </li>

        `;
            });

            serviceBox += `
        </ul>
        </div>
        </div>
        `;
            $('#ps_services').append(serviceBox);
        })
    }

// Function to handle changes in service checkboxes
function handleServiceCheckboxChange() {
    $('#goToDateSelectBtn').prop('disabled', $('.service-checkbox:checked').length === 0);
    const serviceId = $(this).data('id');
    const price = $(this).data('price');
    const duration = $(this).data('duration');
    const serviceName = $(this).data('name');

    if ($(this).is(':checked')) {
        appointment.services.push({ service_id: serviceId, service_name: serviceName, price: price, duration: duration });
    } else {
        appointment.services = appointment.services.filter(service => service.service_id !== serviceId);
    }
    updateTotalDuration();
}

function goToDateTimeSelect(){
    $("#book").modal("hide");
    getDates("previous");
    $("#date-time").modal("show");
}

function goBackToServiceSelect(){
    $("#date-time").modal("hide");
    $('#goToDateSelectBtn').prop('disabled', $('.service-checkbox:checked').length === 0);
    $("#book").modal("show");
}

/**
 * Calculate and update total duration
 */
function updateTotalDuration() {
    const service_list = appointment.services
    const totalDuration = calculateTotalDuration(appointment.services);
    $("#duration").text(totalDuration);
}

/**
 * Calculate the total sum of selected services
 * @param {Array} services - The selected services
 * @returns {number} The total sum
 */
function calculateTotalSum(services) {
    return services.reduce((sum, service) => sum + service.price, 0);
}


/**
 * Render available dates in the date picker
 * @param {Array} availableSlots - The available slots
 */
function renderDates(availableSlots) {
    $("#dateContainer").empty();
    $("#timeSlots").empty();
    const lang_code = $('#cur_lang').val();

    $.each(availableSlots, function (index, item) {
        const dateBtn = $("<button>")
            .addClass("btn btn-outline-secondary day-btn")
            .text(formatDate(item.date, "DD-MM"))
            .on("click", function () {
                $("#dateContainer button").removeClass("btn-primary active");
                $(this).addClass("btn-primary active");
                appointment.date = item.date;
                updateSelectedDateText(appointment.date, lang_code);
                renderTimeSlots(item.slots)
            });
        if (index === 0){
            firstDate = item.date;
            renderTimeSlots(item.slots);
            dateBtn.addClass("btn-primary active");
            updateSelectedDateText(item.date, lang_code);
            appointment.date = item.date;
        }
        lastDate = item.date;
        $("#dateContainer").append(dateBtn);
    })
}

// Function to fetch available dates based on direction (next/previous)
function getDates(direction) {
    const date_param = modifyDate(lastDate, direction === "next" ? 1 : -9);
    const endpoint = `/provider-server/${responseData.server_id}/available-slots/?start_date=${date_param}`;
    $.ajax({
        url: endpoint,
        type: "GET",
        dataType: "json",
        headers: { 'X-CSRFToken': getCookie('csrftoken'), 'X-Signature': signature },
        success: function (response){
            renderDates(response.available_slots)
        },
        error: function (error){
            handleAjaxError(error)
        }
    });
}

// Function to modify date for next/previous date fetching
function modifyDate(dateStr, days) {
    const date = new Date(dateStr);
    date.setDate(date.getDate() + days);
    return date.toISOString().split('T')[0];
}

/**
 * Format a date to full text representation
 * @param {Date} date - The date to format
 * @returns {string} The formatted date
 */
function formatDateFull(date) {
    const options = {weekday: 'long', year: 'numeric', month: 'long', day: 'numeric'};
    return date.toLocaleDateString(undefined, options);
}

function renderTimeSlots(slots) {
    $("#timeSlots").empty();
    // Always start with disabled "next" in the date-time modal until a slot is chosen
    $(".modal-footer .btn-primary").prop("disabled", true);

    if (!Array.isArray(slots) || slots.length === 0) {
        const noSlots = $("<div>").addClass("no-slots").text("No available time slots");
        $("#timeSlots").append(noSlots);
        // Clear previously selected time if switching to a date with no slots
        appointment.time = undefined;
        return;
    }


    $.each(slots, function (index, time) {
        const timeDiv = $("<div>")
            .addClass("time-slot")
            .attr("data-time", time)
            .text(time);

        timeDiv.on("click", function () {
            // Toggle active state among all time-slot elements
            $("#timeSlots .time-slot").removeClass("selected");
            const service_list = appointment.services;
            const totalDuration = calculateTotalDuration(service_list);
            const available = isSlotAvailable(time, totalDuration, slots);
            if (available){
                $(this).addClass("selected");
                // Save the selected time and enable the next/confirm action
                appointment.time = time;
                enableNextOnTimeSelect();
            } else {
                disableNextOnTimeSelect();
                showError("This time slot is not available for the selected services");
            }

        });
        $("#timeSlots").append(timeDiv);
    });
}

// Function to check if a time slot is available
function isSlotAvailable(selectedTime, totalDuration, availableSlots) {
    const startTime = moment(selectedTime, "HH:mm");
    const endTime = startTime.clone().add(totalDuration, "minutes");
    const requiredSlots = [];

    let tempTime = startTime.clone();
    while (tempTime.isBefore(endTime)) {
        requiredSlots.push(tempTime.format("HH:mm"));
        tempTime.add(30, "minutes");
    }

    return requiredSlots.every(slot => availableSlots.includes(slot));
}
/**
 * Enable the next button when a time slot is selected
 */
function enableNextOnTimeSelect() {
    $("#goToConfirmBtn").prop("disabled", false);
}


function disableNextOnTimeSelect() {
    $("#goToConfirmBtn").prop("disabled", true);
}

/**
 * Reset time slots when going back
 */
function resetTimeSlots() {
    $("#timeSlots").empty();
    $(".date-item").removeClass("active");
    $(".time-slot").removeClass("active");
}

/**
 * Handle confirmation method change (phone/email)
 */
function handleConfirmationMethodChange() {
    const isPhone = $(this).attr("id") === "phone-number-tab";

    // Show the corresponding input form
    if (isPhone) {
        $("#phone-number").addClass("show active");
        $("#email").removeClass("show active");
    } else {
        $("#email").addClass("show active");
        $("#phone-number").removeClass("show active");
    }
}

/**
 * Update the confirm button state based on form validity
 */
function updateConfirmButton() {
    const isAgreed = $("#defaultCheck1").is(":checked") || $("#defaultCheck2").is(":checked");
    const isPhoneTab = $("#phone-number-tab").hasClass("active");

    let isValid = isAgreed;

    if (isPhoneTab) {
        const phone = $("#phone").val();
        isValid = isValid && phone.length >= 9;
    } else {
        const email = $("#email").val();
        isValid = isValid && validateEmail(email);
    }

    $(".btn-primary[style*='background-color: #164D35']").prop("disabled", !isValid);
}

/**
 * Validate email format
 * @param {string} email - The email to validate
 * @returns {boolean} Whether the email is valid
 */
function validateEmail(email) {
    const re = /^(([^<>()\[\]\\.,;:\s@"]+(\.[^<>()\[\]\\.,;:\s@"]+)*)|(".+"))@((\[[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\])|(([a-zA-Z\-0-9]+\.)+[a-zA-Z]{2,}))$/;
    return re.test(String(email).toLowerCase());
}

/**
 * Update OTP confirm button state
 */
function updateOTPConfirmButton() {
    const otpCode = $("#otp_code").val();
    $("#otpConfirmBtn").prop("disabled", otpCode.length < 4);
}

/**
 * Send appointment data to confirm
 */
function sendToConfirm() {
    const isPhoneTab = $("#phone-number-tab").hasClass("active");
    const formData = new FormData();

    formData.append('server_id', appointment.server_id);
    formData.append('provider_id', $("#provider_id").val());
    formData.append('appointment_date', appointment.date);
    formData.append('appointment_time', appointment.time);

    appointment.services.forEach((service, index) => {
        formData.append(`services[${index}]`, service.service_id);
    });

    if (isPhoneTab) {
        formData.append('phone', $("#phone").val());
        formData.append('contact_method', 'phone');
    } else {
        formData.append('email', $("#email").val());
        formData.append('contact_method', 'email');
    }

    formData.append('full_name', $("#name").val());
    formData.append('dob', $("#date-birth").val() || $("#dob").val());
    formData.append('gender', $("#genderSelect").val() || $("#genderSelect2").val());
    formData.append('comments', $("#textarea").val() || $("#textarea2").val());

    $.ajax({
        url: '/appointments/create/',
        method: 'POST',
        data: formData,
        processData: false,
        contentType: false,
        headers: {'X-CSRFToken': getCookie('csrftoken')},
        success: function (response) {
            handleAppointmentCreationSuccess(response);
        },
        error: handleAjaxError
    });
}

/**
 * Handle successful appointment creation
 * @param {Object} response - The success response
 */
function handleAppointmentCreationSuccess(response) {
    if (response.success) {
        if (response.requires_otp) {
            showOTPConfirmation(response);
        } else {
            showSuccessMessage();
        }
    } else {
        showError(response.error || "Unknown error occurred");
    }
}

/**
 * Show OTP confirmation form
 * @param {Object} response - The response containing OTP info
 */
function showOTPConfirmation(response) {
    $("#clientConfirmationForm").hide();
    $("#confirmationCodeInput").show();

    const destination = response.otp_sent_to;
    $("#confirmation_destination").text(destination);

    startOTPTimer();
}

/**
 * Start OTP countdown timer
 */
function startOTPTimer() {
    let timeLeft = 60;
    $("#timer").text(timeLeft);

    clearInterval(timerInterval);
    timerInterval = setInterval(function () {
        timeLeft--;
        $("#timer").text(timeLeft);

        if (timeLeft <= 0) {
            clearInterval(timerInterval);
            $("#resendBtn").prop("disabled", false).show();
        }
    }, 1000);
}

/**
 * Confirm OTP code
 */
function confirmOTP() {
    const otpCode = $("#otp_code").val();

    $.ajax({
        url: '/otp/verify/',
        method: 'POST',
        data: {
            otp_code: otpCode,
            appointment_id: appointment.appointment_id
        },
        headers: {'X-CSRFToken': getCookie('csrftoken')},
        success: function (response) {
            if (response.success) {
                showSuccessMessage();
            } else {
                showError(response.error || "Invalid OTP code");
            }
        },
        error: handleAjaxError
    });
}

/**
 * Show success message after confirmation
 */
function showSuccessMessage() {
    $("#confirmationCodeInput, #clientConfirmationForm").hide();
    $(".confirmationSuccess").show();
    clearInterval(timerInterval);
}

/**
 * Resend OTP code
 */
function resendOTP() {
    $.ajax({
        url: '/otp/resend/',
        method: 'POST',
        data: {
            appointment_id: appointment.appointment_id
        },
        headers: {'X-CSRFToken': getCookie('csrftoken')},
        success: function (response) {
            if (response.success) {
                $("#resendBtn").prop("disabled", true).hide();
                startOTPTimer();
            } else {
                showError(response.error || "Failed to resend code");
            }
        },
        error: handleAjaxError
    });
}

/**
 * Format a date to the specified format
 * @param {Date} date - The date to format
 * @param {string} format - The format string
 * @returns {string} The formatted date
 */
function formatDate(date, format) {
    const d = new Date(date);
    const year = d.getFullYear();
    const month = String(d.getMonth() + 1).padStart(2, '0');
    const day = String(d.getDate()).padStart(2, '0');

    if (format === 'YYYY-MM-DD') {
        return `${year}-${month}-${day}`;
    } else if (format === 'DD-MM') {
        return `${day}-${month}`;
    } else if (format === 'DD.MM.YYYY') {
        return `${day}.${month}.${year}`;
    }

    return `${year}-${month}-${day}`;
}

/**
 * Get a cookie by name (for CSRF token)
 * @param {string} name - The cookie name
 * @returns {string} The cookie value
 */
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

/**
 * Handle AJAX errors
 * @param {Object} error - The error object
 */
function handleAjaxError(error) {
    console.error("AJAX Error:", error);
    let errorMessage = "An error occurred while processing your request.";

    if (error.responseJSON && error.responseJSON.error) {
        errorMessage = error.responseJSON.error;
    } else if (error.statusText) {
        errorMessage = error.statusText;
    }

    showError(errorMessage);
}

/**
 * Show error message
 * @param {string} message - The error message
 */
function showError(message) {
    alert(message);
}

// Function to close the modal and reset data
function closeModal() {
    $('#book').modal("hide");
    resetAppointmentData();
    // resetOTPInput();
}

// Utility function to reset appointment and response data
function resetAppointmentData() {
    appointment.services = [];
    responseData = {};
}

// Function to calculate the total duration of selected services
function calculateTotalDuration(services) {
    return services.reduce((sum, service) => sum + service.duration, 0);
}

// Function to update the selected date text with appropriate formatting
function updateSelectedDateText(dateStr, lang_code) {
    const date = new Date(dateStr);
    const day = date.getDate();

    // Get month name based on language code
    let monthName;
    const monthIndex = date.getMonth();

    if (lang_code === 'uz') {
        const uzMonths = ['YAN', 'FEV', 'MAR', 'APR', 'MAY', 'IYUN', 'IYUL', 'AVG', 'SEN', 'OKT', 'NOY', 'DEK'];
        monthName = uzMonths[monthIndex];
    } else if (lang_code === 'ru') {
        const ruMonths = ['ЯНВ', 'ФЕВ', 'МАР', 'АПР', 'МАЙ', 'ИЮНЬ', 'ИЮЛЬ', 'АВГ', 'СЕН', 'ОКТ', 'НОЯ', 'ДЕК'];
        monthName = ruMonths[monthIndex];
    } else {
        const enMonths = ['JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN', 'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC'];
        monthName = enMonths[monthIndex];
    }

    // Get weekday name based on language code
    let weekdayName;
    const weekdayIndex = date.getDay();

    if (lang_code === 'uz') {
        const uzWeekdays = ['Yakshanba', 'Dushanba', 'Seshanba', 'Chorshanba', 'Payshanba', 'Juma', 'Shanba'];
        weekdayName = uzWeekdays[weekdayIndex];
    } else if (lang_code === 'ru') {
        const ruWeekdays = ['Воскресенье', 'Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота'];
        weekdayName = ruWeekdays[weekdayIndex];
    } else {
        const enWeekdays = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];
        weekdayName = enWeekdays[weekdayIndex];
    }

    // Update the selected date text
    $('#selectedDateText').text(`${day} ${monthName}, ${weekdayName}`);
}

function goToConfirm(){
    // Populate confirm modal details from the appointment object before showing
    renderConfirm();
    $("#date-time").modal("hide");
    $("#book").modal("hide");
    $("#confirm").modal("show");
}

function renderConfirm(){
    try {
        // Time and Date
        if (appointment.time) {
            $("#appointment_time").text(appointment.time);
        }
        if (appointment.date) {
            $("#appointment_date").text(formatDate(appointment.date, 'DD.MM.YYYY'));
        }

        // Services list
        const $list = $("#appointment_services");
        $list.empty();
        if (Array.isArray(appointment.services)) {
            appointment.services.forEach(svc => {
                const priceText = Number(svc.price).toLocaleString();
                const $li = $(
                    `<li>
                        <p></p>
                        <div class="d-flex align-items-center justify-content-end" style="gap: 10px;">
                          <span></span>
                          <div class="time"><img src="/static/design/images/clock-grey.svg" alt="icon"><p></p></div>
                        </div>
                      </li>`
                );
                $li.find('p').first().text(svc.service_name || '');
                $li.find('span').text(priceText);
                $li.find('.time p').text(`${svc.duration} min`);
                $list.append($li);
            });
        }

        // Duration
        const totalDuration = calculateTotalDuration(appointment.services || []);
        $("#appointment_duration").text(totalDuration);

        // Total amount
        const totalAmount = calculateTotalSum(appointment.services || []);
        $("#appointment_total").text(Number(totalAmount).toLocaleString());

        // Specialist label is already set elsewhere (#confirmLabel), no change here
    } catch (e) {
        console.error('Error rendering confirm modal:', e);
    }
}

function selectConfirmByPhone(){
    $("#confirm_by_email").removeClass("active");
    $("#confirm_by_phone").addClass("active");
    $("#phone_field").show();
    $("#email_field").hide();
}

function selectConfirmByEmail(){
    $("#confirm_by_phone").removeClass("active");
    $("#confirm_by_email").addClass("active");
    $("#phone_field").hide();
    $("#email_field").show();
}

function checkPhoneInput(){
    const phoneValue = $(this).val();
    if (phoneValue.length > 8){
        searchClient({phone_number: phoneValue});
    } else {
        $('#client_form_field').hide();
    }
}

// Check if the email input is valid
function checkEmailInput() {
    const emailValue = $(this).val();
    if (isValidEmail(emailValue)) {
        searchClient({email: emailValue});
    } else {
        $('.client_form_field').hide();
    }
}
// Helper function to validate email
function isValidEmail(email) {
    // Basic email validation regex
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return emailRegex.test(email);
}

function searchClient(search_data){
    const signature = $('#signature').val();
        $.ajax({
            url: '/client/search/',
            type: 'GET',
            data: search_data,
            headers: {
                'X-CSRFToken': getCookie('csrftoken'),
                'X-Signature': signature
            },
            success: function (response) {
                if (response.success) {
                    //fill form inputs
                    $('#full_name').val(response.client_full_name)
                    $('#dob').val(response.client_dob)
                    $('#sex').val(response.client_sex)
                    $('#client_id').val(response.client_id)
                    //show client info block
                    $('#enter_text').hide()
                    $('#clientFound').show()
                    $('#client_form_field').show();

                }
            },
            error: function (error) {
                console.log(error.responseText)
                $('#full_name').val("")
                $('#dob').val("")
                $('#sex').val("")
                $('#client_id').val("")
                $('#clientNotFound').show()
                $('#clientFound').hide()
                $('#client_form_field').show();
           }
        });
}




