  const toggleBtn = document.getElementById("langToggle");
  const dropdown = document.getElementById("langDropdown");
  const currentFlag = document.getElementById("currentFlag");
  const currentLang = document.getElementById("currentLang");

  const defaultLanguage = {
    lang: "UZ",
    flag: "static/design/images/uzbekistan.svg"
  };

  // Load language from localStorage or use default
  function loadLanguage() {
    const savedLang = localStorage.getItem("lang");
    const savedFlag = localStorage.getItem("flag");

    if (savedLang && savedFlag) {
      currentLang.textContent = savedLang;
      currentFlag.src = savedFlag;
    } else {
      // Set default
      currentLang.textContent = defaultLanguage.lang;
      currentFlag.src = defaultLanguage.flag;
    }
  }

  // Save selected language to localStorage
  function saveLanguage(lang, flag) {
    localStorage.setItem("lang", lang);
    localStorage.setItem("flag", flag);
  }

  // Initialize on page load
  window.addEventListener("DOMContentLoaded", loadLanguage);

  toggleBtn.addEventListener("click", () => {
    dropdown.classList.toggle("show");
  });

  document.querySelectorAll(".lang-option").forEach(option => {
    option.addEventListener("click", () => {
      const lang = option.getAttribute("data-lang");
      const flag = option.getAttribute("data-flag");

      currentLang.textContent = lang;
      currentFlag.src = flag;

      saveLanguage(lang, flag); // 🔐 Save it

      dropdown.classList.remove("show");

      // Optional: trigger language change logic here
      $('#cur_lang').val(lang.toLowerCase())
      $('#setlangform').submit();
    });
  });

  // Close dropdown on outside click
  document.addEventListener("click", (e) => {
    if (!toggleBtn.contains(e.target) && !dropdown.contains(e.target)) {
      dropdown.classList.remove("show");
    }
  });
  
  /*******************************************/
  
  document.addEventListener("DOMContentLoaded", function () {
    const images = document.querySelectorAll('.carousel-item img');

    images.forEach(img => {
      // Wait until image is fully loaded
      img.onload = () => {
        const ratio = img.naturalWidth / img.naturalHeight;

        if (ratio >= 1440 / 600) {
          // Wider image → fill height, crop sides
          img.classList.add('fill-height');
        } else {
          // Taller image → fill width, crop top/bottom
          img.classList.add('fill-width');
        }
      };

      // Trigger manually in case image is cached
      if (img.complete) img.onload();
    });
  });


  /**************************************/


$(function () {
  $('[data-toggle="popover"]').popover()
})


/*********************************/
// const cards = document.querySelectorAll('.card');

//   cards.forEach(card => {
//     card.addEventListener('mouseenter', () => {
//       const rowTop = card.getBoundingClientRect().top;

//       // Найти карточки в той же строке
//       const sameRowCards = Array.from(cards).filter(c =>
//         Math.abs(c.getBoundingClientRect().top - rowTop) < 5
//       );

//       // Установить ширины: hovered = 420px, остальные делят оставшееся
//       const gap = 20;
//       const fullRowWidth = 1400 - gap * 4;
//       const hoveredWidth = 420;
//       const remainingWidth = fullRowWidth - hoveredWidth;
//       const restWidth = remainingWidth / (sameRowCards.length - 1);

//       sameRowCards.forEach(c => {
//         if (c === card) {
//           c.style.flex = `0 0 ${hoveredWidth}px`;
//         } else {
//           c.style.flex = `0 0 ${restWidth}px`;
//         }
//       });
//     });

//     card.addEventListener('mouseleave', () => {
//       cards.forEach(c => {
//         c.style.flex = '0 0 calc((100% - 4 * 20px) / 5)';
//       });
//     });
//   });
    const container = document.querySelector('.card-container');
    const cards = document.querySelectorAll('.card');

    function getRowCards(card) {
      const top = card.getBoundingClientRect().top;
      return Array.from(cards).filter(c =>
        Math.abs(c.getBoundingClientRect().top - top) < 5
      );
    }

    function getExpectedCardsPerRow() {
      const width = window.innerWidth;
      if (width >= 1440) return 5;
      if (width >= 1024) return 4;
      if (width >= 768) return 3;
      return 0; // No hover for < 768px
    }

    function isHoverEnabled() {
      return window.innerWidth >= 768;
    }

    cards.forEach(card => {
      card.addEventListener('mouseenter', () => {
        if (!isHoverEnabled()) return;

        const rowCards = getRowCards(card);
        const expectedCards = getExpectedCardsPerRow();
        if (expectedCards === 0) return;

        const hoveredWidth = 420;
        const gap = 20;
        const totalGap = gap * (expectedCards - 1);
        const containerWidth = container.clientWidth;
        const remainingWidth = containerWidth - totalGap - hoveredWidth;
        const otherCardWidth = remainingWidth / (expectedCards - 1);

        rowCards.forEach((c, index) => {
          if (c === card) {
            c.style.flex = `0 0 ${hoveredWidth}px`;
          } else if (index < expectedCards) {
            c.style.flex = `0 0 ${otherCardWidth}px`;
          }
        });
      });

      card.addEventListener('mouseleave', () => {
        cards.forEach(c => c.style.flex = '');
      });
    });

    window.addEventListener('resize', () => {
      cards.forEach(c => c.style.flex = '');
    });



    /**************************************/
    const duration = parseInt(document.getElementById('duration').textContent);
    const slotDuration = 30;
    const slotCount = duration / slotDuration;
    const times = ["09:00", "09:30", "10:00", "10:30", "11:00", "11:30", "13:00", "13:30", "14:00", "14:30", "15:00", "15:30", "16:00", "16:30", "17:00", "17:30"];
    const unavailableSlots = ["10:00"];

    const visibleCount = 3;
    let currentStartIndex = 0;
    let allButtons = [];

    const generateDates = () => {
      allButtons = [];
      const today = new Date();
      for (let i = 0; i < 20; i++) {
        const date = new Date();
        date.setDate(today.getDate() + i);
        if (date.getDay() === 0 || date.getDay() === 6) continue;

        const btn = document.createElement('button');
        btn.className = 'btn btn-outline-secondary day-btn';
        btn.textContent = date.toLocaleDateString('en-GB', { day: '2-digit', month: '2-digit' });
        btn.dataset.date = date.toISOString().split('T')[0];
        btn.dataset.full = date.toLocaleDateString('en-US', { day: '2-digit', month: 'short', weekday: 'long' }).toUpperCase();
        btn.onclick = () => selectDate(btn);
        allButtons.push(btn);
      }
      renderDateButtons();
      if (allButtons.length) allButtons[0].click();
    };

    const renderDateButtons = () => {
      const container = document.getElementById('dateContainer');
      container.innerHTML = '';
      const visibleButtons = allButtons.slice(currentStartIndex, currentStartIndex + visibleCount);
      visibleButtons.forEach(btn => container.appendChild(btn));
    };

    document.getElementById('prevDateBtn').onclick = () => {
      if (currentStartIndex > 0) {
        currentStartIndex--;
        renderDateButtons();
      }
    };

    document.getElementById('nextDateBtn').onclick = () => {
      if (currentStartIndex + visibleCount < allButtons.length) {
        currentStartIndex++;
        renderDateButtons();
      }
    };

    const selectDate = (btn) => {
      document.querySelectorAll('.day-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');

      const display = document.getElementById('selectedDateText');
      const full = new Date(btn.dataset.date);
      const formatted = `${full.getDate()} ${full.toLocaleDateString('en-US', { month: 'short' }).toUpperCase()}, ${full.toLocaleDateString('en-US', { weekday: 'long' })}`;
      display.textContent = formatted;

      renderTimeSlots();
    };

    const renderTimeSlots = () => {
      const container = document.getElementById('timeSlots');
      container.innerHTML = '';

      for (let i = 0; i < times.length; i++) {
        const slotBtn = document.createElement('div');
        slotBtn.className = 'time-slot';
        slotBtn.textContent = times[i];

        const slotRange = times.slice(i, i + slotCount);
        const isRangeAvailable = slotRange.length === slotCount && slotRange.every(time => !unavailableSlots.includes(time));

        if (!isRangeAvailable || slotRange.length < slotCount) {
          slotBtn.classList.add('disabled');
        } else {
          slotBtn.onclick = () => selectTime(slotRange);
        }

        slotBtn.onmouseenter = () => {
          clearHover();
          if (slotRange.length === slotCount) {
            const children = Array.from(container.children);
            for (let j = 0; j < slotCount; j++) {
              if (i + j < children.length) {
                children[i + j].classList.add('hover-range');
              }
            }
          }
        };

        slotBtn.onmouseleave = clearHover;

        container.appendChild(slotBtn);
      }
    };

    const clearHover = () => {
      document.querySelectorAll('.time-slot').forEach(btn => btn.classList.remove('hover-range'));
    };

    const selectTime = (range) => {
      document.querySelectorAll('.time-slot').forEach(btn => btn.classList.remove('selected'));
      const container = document.getElementById('timeSlots');
      const children = Array.from(container.children);

      for (let i = 0; i < children.length; i++) {
        if (children[i].textContent === range[0]) {
          for (let j = 0; j < range.length; j++) {
            children[i + j].classList.add('selected');
          }
          break;
        }
      }
    };

    generateDates();

/**************/
 // Initialize all inputs with class "date-picker"
  document.querySelectorAll('.date-picker').forEach(input => {
    flatpickr(input, {
      dateFormat: "d.m.Y",
      maxDate: "today",
      defaultDate: null
    });
  });

  // Open calendar when icon is clicked
  document.querySelectorAll('.calendar-icon').forEach((icon, index) => {
    icon.addEventListener('click', () => {
      const input = icon.parentElement.querySelector('.date-picker');
      if (input && input._flatpickr) {
        input._flatpickr.open();
      }
    });
  });

  // Global variables for managing appointment data and related operations
  const appointment = { services: [] };
  appointment.provider_identifier = "{{ provider.identifier }}"
  let responseData = {};
  let lastDate;
  let firstDate;
  const cur_lang = document.getElementById('cur_lang').value;
  const signature = "{{ signature }}";
  const LOCALE_FORMAT = {
    uz: "YYYY-MM-DD",
    ru: "YYYY-MM-DD",
    en: "YYYY-MM-DD",
  }

  // Utility function to show error or success messages
    function showToast(message, type = "info") {
        // Define Bootstrap toast classes for different types
        const toastClasses = {
            success: "bg-success text-white",
            error: "bg-danger text-white",
            info: "bg-primary text-white",
            warning: "bg-warning text-dark"
        };

        // Remove existing toasts to prevent stacking issues
        $(".toast-container .toast").remove();

        // Create the toast dynamically
        const toastHTML = `
    <div class="toast align-items-center ${toastClasses[type] || toastClasses.info} border-0 shadow" role="alert" aria-live="assertive" aria-atomic="true" data-bs-autohide="true">
      <div class="d-flex">
        <div class="toast-body">
          ${message}
        </div>
        <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
      </div>
    </div>`;

        // Append the toast container if not already present
        if ($(".toast-container").length === 0) {
            $("body").append('<div class="toast-container position-fixed top-0 end-0 p-3"></div>');
        }

        // Append the toast inside the container
        $(".toast-container").append(toastHTML);

        // Initialize and show the toast
        var toastElement = $(".toast").last();
        var toast = new bootstrap.Toast(toastElement[0]);
        toast.show();
    }

  $(document).ready(function () {

  });