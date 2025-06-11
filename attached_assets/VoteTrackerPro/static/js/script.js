// Main JavaScript for the voting application
document.addEventListener('DOMContentLoaded', function() {
  // Setup voting form validation
  setupVotingForm();

  // Setup admin dashboard if it exists
  if (document.querySelector('.vote-stats')) {
    setupAdminDashboard();
  }

  // Setup countdown checker for winner declaration
  setupCountdownChecker();

  // Setup flash message auto-hide
  setupFlashMessages();
});

function setupVotingForm() {
  const voterIdInput = document.getElementById('main_voter_id');
  const forms = document.querySelectorAll('.party-box form');

  if (!voterIdInput || !forms.length) return;

  // Add validation to each form
  forms.forEach(form => {
    form.addEventListener('submit', validateForm);
  });

  function validateForm(event) {
    const voterId = voterIdInput.value.trim();

    if (!voterId || voterId.length < 8 || voterId.length > 9 || !/^\d+$/.test(voterId)) {
      event.preventDefault();
      alert('Please enter a valid 8 to 9-digit Voter ID');
      return false;
    }

    // Copy the voter ID to the hidden field in the form
    const index = Array.from(forms).indexOf(this) + 1;
    document.getElementById(`voter_id_${index}`).value = voterId;

    return true;
  }
}

function createConfetti() {
  // This function will be implemented on the winner page
  // for the celebration effects
}

function setupAdminDashboard() {
  // Toggle sections in admin dashboard
  const toggleButtons = document.querySelectorAll('.control-form h3');

  toggleButtons.forEach(button => {
    button.addEventListener('click', function() {
      const form = this.nextElementSibling;
      if (form.style.display === 'none') {
        form.style.display = 'block';
      } else {
        form.style.display = 'none';
      }
    });
  });
  
  // Start auto-refresh of dashboard data
  refreshDashboardData();
}

function setupCountdownChecker() {
  // Check if winner needs to be declared (for AJAX updates)
  if (window.location.pathname === '/') {
    setInterval(function() {
      fetch('/check_winner_status')
        .then(response => response.json())
        .then(data => {
          if (data.redirect) {
            window.location.href = data.redirect;
          }
        })
        .catch(error => console.error('Error checking winner status:', error));
    }, 5000); // Check every 5 seconds
  }
}

function setupFlashMessages() {
  // Auto-hide flash messages after 5 seconds
  const flashMessages = document.querySelectorAll('.success, .error, .warning, .info');

  flashMessages.forEach(message => {
    setTimeout(() => {
      message.style.opacity = '0';
      setTimeout(() => {
        message.style.display = 'none';
      }, 500);
    }, 5000);
  });
}
function exportToExcel(tableId) {
  try {
    // Get the table data
    const table = document.getElementById(tableId);
    if (!table) {
      console.error('Table not found:', tableId);
      return;
    }

    let csv = [];
    const rows = table.getElementsByTagName('tr');

    for (let i = 0; i < rows.length; i++) {
      let row = [], cols = rows[i].getElementsByTagName('td');
      if (cols.length === 0) cols = rows[i].getElementsByTagName('th');

      for (let j = 0; j < cols.length; j++) {
        // Properly escape and quote CSV values
        let text = cols[j].innerText.replace(/"/g, '""');
        row.push(`"${text}"`);
      }
      csv.push(row.join(","));
    }

    // Create and trigger download
    const csvContent = "data:text/csv;charset=utf-8," + encodeURIComponent(csv.join("\n"));
    const link = document.createElement("a");
    link.setAttribute("href", csvContent);
    link.setAttribute("download", tableId === 'voters-table' ? "voting_data.csv" : "party_data.csv");
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  } catch (error) {
    console.error('Error exporting to Excel:', error);
    alert('Failed to export to Excel. Please try again.');
  }
}

function exportToPDF(tableId) {
  try {
    const element = document.getElementById(tableId);
    if (!element) {
      console.error('Table not found:', tableId);
      return;
    }

    const opt = {
      margin: 0.5,
      filename: tableId === 'voters-table' ? 'voting_data.pdf' : 'party_data.pdf',
      image: { type: 'jpeg', quality: 1 },
      html2canvas: { 
        scale: 2,
        logging: true,
        useCORS: true
      },
      jsPDF: { 
        unit: 'in', 
        format: 'a4', 
        orientation: 'landscape'
      }
    };

    // Add loading indicator
    const loadingDiv = document.createElement('div');
    loadingDiv.innerHTML = 'Generating PDF...';
    loadingDiv.style.position = 'fixed';
    loadingDiv.style.top = '50%';
    loadingDiv.style.left = '50%';
    loadingDiv.style.transform = 'translate(-50%, -50%)';
    loadingDiv.style.padding = '20px';
    loadingDiv.style.background = 'rgba(0,0,0,0.7)';
    loadingDiv.style.color = 'white';
    loadingDiv.style.borderRadius = '5px';
    loadingDiv.style.zIndex = '9999';
    document.body.appendChild(loadingDiv);

    html2pdf().set(opt).from(element).save().then(() => {
      document.body.removeChild(loadingDiv);
    }).catch(error => {
      console.error('Error generating PDF:', error);
      document.body.removeChild(loadingDiv);
      alert('Failed to generate PDF. Please try again.');
    });
  } catch (error) {
    console.error('Error exporting to PDF:', error);
    alert('Failed to export to PDF. Please try again.');
  }
}

// Keep existing table data during AJAX refresh
function updateTableData(newData) {
  if (!newData.all_voters) return;

  // Update voters table
  const tbody = document.querySelector('.voters-table tbody');
  if (tbody) {
    tbody.innerHTML = newData.all_voters.map(voter => `
      <tr>
        <td>${voter.voter_id}</td>
        <td>${voter.name}</td>
        <td>${voter.party}</td>
        <td>${voter.voted_at}</td>
      </tr>
    `).join('');
  }
  
  // Update vote stats
  if (newData.vote_data) {
    // Update total counts
    const totalVotersElem = document.getElementById('total-voters-count');
    const totalVotesElem = document.getElementById('total-votes-count');
    
    if (totalVotersElem) totalVotersElem.textContent = newData.total_voters;
    if (totalVotesElem) totalVotesElem.textContent = newData.total_votes;
    
    // Update party-specific vote counts and percentages
    for (const [party, data] of Object.entries(newData.vote_data)) {
      const countElem = document.querySelector(`.vote-count-${party.replace(/\s+/g, '-')}`);
      const percentElem = document.querySelector(`.vote-percent-${party.replace(/\s+/g, '-')}`);
      
      if (countElem) countElem.textContent = data.count;
      if (percentElem) percentElem.textContent = `${data.percentage}%`;
    }
  }
}

function refreshDashboardData() {
  // Don't refresh on login page
  if ($('.login-form').length) {
    return;
  }

  $.ajax({
    url: '/api/admin/dashboard_data',
    type: 'GET',
    dataType: 'json',
    timeout: 5000,
    success: function(data) {
      updateTableData(data);
      setTimeout(refreshDashboardData, 3000); // Refresh every 3 seconds on success
    },
    error: function(error) {
      console.error("Error updating dashboard:", error);
      // Retry after 5 seconds on error
      setTimeout(refreshDashboardData, 5000);
    }
  });
}