$(document).ready(function () {
    // Initialize components
    initializeComponents();

    // Set up event listeners
    setupEventListeners();
});

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

    // Server selection
    $(document).on("click", ".service-checkbox", function () {
        updateNextButtonState();
    });

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
            console.log(response)
            responseData = response;
            appointment.server_id = serverId;
            fillServices(response.service_types, lang_code);
            // renderDates(response.available_time_slots);
            // Show the booking modal
            $("#book").modal("show");
        },
        error: function (error) {
            handleAjaxError(error)
        }
    });

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
        <li class="list-group-item">
          <p>${serviceName}</p>
          <div class="d-flex align-items-center justify-content-end">
            <span>> ${price.toLocaleString()}</span>
            <div class="form-check">
              <input class="form-check-input position-static " 
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

    // Show the booking modal
    $("#book").modal("show");
}

/**
 * Fetch services for the selected server
 * @param {string} serverId - The server ID
 */
function fetchServerServices(serverId) {
    $.ajax({
        url: `/provider-server/${serverId}/services/`,
        method: 'GET',
        dataType: 'json',
        headers: {'X-CSRFToken': getCookie('csrftoken')},
        success: function (response) {
            console.log(response);
            // renderServerServices(response);
        },
        error: handleAjaxError
    });
}

/**
 * Render services available for the server
 * @param {Object} response - The response containing services
 */
function renderServerServices(response) {
    responseData = response;

    // Clear existing checkboxes
    $(".service-checkbox").prop("checked", false);

    // Populate each service in its category
    if (response.services && response.services.length > 0) {
        // Services are already rendered in the modal, just make sure checkboxes work
        setupServiceCheckboxes();
    }
}

/**
 * Setup service checkboxes for selection
 */
function setupServiceCheckboxes() {
    $(".form-check-input").on("change", function () {
        const serviceId = $(this).val();
        const price = $(this).data("price");
        const duration = $(this).data("duration") || 60;
        const serviceName = $(this).closest("li").find("p").text();

        if ($(this).is(":checked")) {
            appointment.services.push({
                service_id: serviceId,
                service_name: serviceName,
                price: parseFloat(price),
                duration: parseInt(duration)
            });
        } else {
            appointment.services = appointment.services.filter(service =>
                service.service_id !== serviceId
            );
        }

        updateNextButtonState();
        updateTotalDuration();
    });
}

/**
 * Update next button state based on service selection
 */
function updateNextButtonState() {
    $(".btn-primary[data-dismiss='modal'][data-toggle='modal'][data-target='#date-time']")
        .prop("disabled", appointment.services.length === 0);
}

/**
 * Calculate and update total duration
 */
function updateTotalDuration() {
    const totalDuration = calculateTotalDuration(appointment.services);
    $("#duration").text(totalDuration);
}

/**
 * Calculate the total duration of selected services
 * @param {Array} services - The selected services
 * @returns {number} The total duration
 */
function calculateTotalDuration(services) {
    return services.reduce((sum, service) => sum + service.duration, 0);
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
 * Fetch available dates for the selected server
 * @param {string} direction - The direction to fetch dates (next/previous)
 */
function getDates(direction) {
    const date = new Date();
    date.setDate(date.getDate() + (direction === "next" ? 7 : -7));

    const formattedDate = formatDate(date, 'YYYY-MM-DD');

    $.ajax({
        url: `/provider-server/${appointment.server_id}/available-slots/?start_date=${formattedDate}`,
        method: 'GET',
        dataType: 'json',
        headers: {'X-CSRFToken': getCookie('csrftoken')},
        success: function (response) {
            renderDates(response.available_slots);
        },
        error: handleAjaxError
    });
}

/**
 * Render available dates in the date picker
 * @param {Array} availableSlots - The available slots
 */
function renderDates(availableSlots) {
    const $dateContainer = $("#dateContainer");
    $dateContainer.empty();

    availableSlots.forEach((slot, index) => {
        const date = new Date(slot.date);
        const day = date.getDate();
        const month = date.toLocaleString('default', {month: 'short'});
        const weekday = date.toLocaleString('default', {weekday: 'short'});

        const $dateBtn = $(`
            <div class="date-item" data-date="${slot.date}">
                <span class="weekday">${weekday}</span>
                <span class="day">${day}</span>
                <span class="month">${month}</span>
            </div>
        `);

        if (index === 0) {
            $dateBtn.addClass("active");
            appointment.date = slot.date;
            renderTimeSlots(slot.slots);
            $("#selectedDateText").text(formatDateFull(date));
        }

        $dateBtn.on("click", function () {
            $(".date-item").removeClass("active");
            $(this).addClass("active");
            appointment.date = slot.date;
            renderTimeSlots(slot.slots);
            $("#selectedDateText").text(formatDateFull(date));
        });

        $dateContainer.append($dateBtn);
    });
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

/**
 * Render time slots for the selected date
 * @param {Array} slots - The available time slots
 */
function renderTimeSlots(slots) {
    const $timeSlots = $("#timeSlots");
    $timeSlots.empty();

    slots.forEach(time => {
        const $timeBtn = $(`<div class="time-slot">${time}</div>`);

        $timeBtn.on("click", function () {
            $(".time-slot").removeClass("active");
            $(this).addClass("active");
            appointment.time = time;
            enableNextButton();
        });

        $timeSlots.append($timeBtn);
    });
}

/**
 * Enable the next button when a time slot is selected
 */
function enableNextButton() {
    $(".modal-footer .btn-primary").prop("disabled", false);
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