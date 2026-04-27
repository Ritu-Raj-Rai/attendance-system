// Get CSRF token
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

// Global variables
let selectedDate = null;
let selectedStatus = null;

// Initialize when page loads
document.addEventListener('DOMContentLoaded', function() {
    // Add click handlers to calendar cells
    document.querySelectorAll('.calendar-cell[data-date]').forEach(cell => {
        cell.addEventListener('click', function(e) {
            const date = this.getAttribute('data-date');
            if (date) {
                // Remove selected class from all cells
                document.querySelectorAll('.calendar-cell').forEach(c => {
                    c.classList.remove('selected');
                });
                // Add selected class to clicked cell
                this.classList.add('selected');
                showModal(date);
            }
        });
    });
    
    // Modal close button
    const modalClose = document.querySelector('.modal-close');
    if (modalClose) {
        modalClose.addEventListener('click', closeModal);
    }
    
    // Cancel button in modal
    const cancelBtn = document.getElementById('modalCancel');
    if (cancelBtn) {
        cancelBtn.addEventListener('click', closeModal);
    }
    
    // Option buttons in modal
    const buttons = document.querySelectorAll('.btn-option');
    buttons.forEach(button => {
        button.addEventListener('click', function(e) {
            e.preventDefault();
            const status = this.getAttribute('data-status');
            handleOptionClick(this, status);
        });
    });
    
    // Close modal when clicking outside
    const modal = document.getElementById('markModal');
    if (modal) {
        modal.addEventListener('click', function(e) {
            if (e.target === this) {
                closeModal();
            }
        });
    }
});

function showModal(date) {
    selectedDate = date;
    selectedStatus = null;
    
    const modal = document.getElementById('markModal');
    const dateElement = document.getElementById('modalDate');
    
    // Format date for display
    const dateObj = new Date(date);
    const options = { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' };
    const formattedDate = dateObj.toLocaleDateString('en-US', options);
    
    dateElement.textContent = formattedDate;
    
    // Reset button styles
    document.querySelectorAll('.btn-option').forEach(btn => {
        btn.classList.remove('active');
    });
    
    // Show modal
    modal.classList.add('show');
}

function closeModal() {
    const modal = document.getElementById('markModal');
    modal.classList.remove('show');
    
    // Remove selected class from all cells when closing modal
    document.querySelectorAll('.calendar-cell').forEach(cell => {
        cell.classList.remove('selected');
    });
    
    selectedDate = null;
    selectedStatus = null;
    
    // Reset button styles
    document.querySelectorAll('.btn-option').forEach(btn => {
        btn.classList.remove('active');
    });
}

function handleOptionClick(button, status) {
    // Remove active class from all buttons
    document.querySelectorAll('.btn-option').forEach(btn => {
        btn.classList.remove('active');
    });
    
    // Add active class to clicked button
    button.classList.add('active');
    selectedStatus = status;
    
    // If not clear option, submit immediately
    if (status !== 'clear') {
        submitAttendance(status);
    } else {
        // For clear option, give user time to confirm
        setTimeout(() => {
            submitAttendance(status);
        }, 300);
    }
}

function submitAttendance(status) {
    if (!selectedDate) {
        alert('No date selected');
        return;
    }
    
    // Show loading state
    const submitBtn = document.querySelector('.btn-option.active');
    if (submitBtn) {
        submitBtn.disabled = true;
    }
    
    fetch(window.location.href, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-Requested-With': 'XMLHttpRequest',
            'X-CSRFToken': getCookie('csrftoken')
        },
        body: JSON.stringify({
            date: selectedDate,
            status: status
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            // Update the calendar cell with new color
            updateCalendarCell(selectedDate, status);
            
            // Remove selected class
            document.querySelectorAll('.calendar-cell').forEach(cell => {
                cell.classList.remove('selected');
            });
            
            // Close modal after short delay
            setTimeout(() => {
                closeModal();
            }, 500);
        } else {
            alert('Failed to mark attendance: ' + (data.error || 'Unknown error'));
            if (submitBtn) {
                submitBtn.disabled = false;
            }
        }
    })
    .catch(error => {
        console.error('Error:', error);
        alert('Error marking attendance. Please try again.');
        if (submitBtn) {
            submitBtn.disabled = false;
        }
    });
}

function updateCalendarCell(date, status) {
    const cell = document.querySelector(`[data-date="${date}"]`);
    if (!cell) return;
    
    // Remove old status classes
    cell.classList.remove('status-present', 'status-absent', 'status-excused');
    
    // Add new status class
    if (status === 'clear') {
        // Clear - remove all status classes, keep white background
        const icon = cell.querySelector('.status-icon');
        if (icon) {
            icon.remove();
        }
    } else if (status === 'present') {
        cell.classList.add('status-present');
        // Update or create icon
        let icon = cell.querySelector('.status-icon');
        if (icon) {
            icon.remove();
        }
        const iconHtml = '<i class="fas fa-check-circle status-icon" style="color: #10b981;" aria-label="Present"></i>';
        const dayDiv = cell.querySelector('.calendar-day');
        dayDiv.insertAdjacentHTML('afterend', iconHtml);
    } else if (status === 'absent') {
        cell.classList.add('status-absent');
        // Update or create icon
        let icon = cell.querySelector('.status-icon');
        if (icon) {
            icon.remove();
        }
        const iconHtml = '<i class="fas fa-times-circle status-icon" style="color: #f43f5e;" aria-label="Absent"></i>';
        const dayDiv = cell.querySelector('.calendar-day');
        dayDiv.insertAdjacentHTML('afterend', iconHtml);
    } else if (status === 'excused') {
        cell.classList.add('status-excused');
        // Update or create icon
        let icon = cell.querySelector('.status-icon');
        if (icon) {
            icon.remove();
        }
        const iconHtml = '<i class="fas fa-info-circle status-icon" style="color: #f59e0b;" aria-label="Excused"></i>';
        const dayDiv = cell.querySelector('.calendar-day');
        dayDiv.insertAdjacentHTML('afterend', iconHtml);
    }
}
