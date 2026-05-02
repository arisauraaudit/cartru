// Paste a Listing Feature - External File
// Add this to index.html: <script src="paste-listing.js" defer></script>

(function() {
  // Function to toggle the paste input visibility
  window.togglePasteInput = function() {
    const expanded = document.getElementById('pasteListingExpanded');
    if (expanded) {
      const isVisible = expanded.style.display === 'block';
      expanded.style.display = isVisible ? 'none' : 'block';
      if (!isVisible && document.getElementById('listingUrlInput')) {
        document.getElementById('listingUrlInput').focus();
      }
    }
  };

  // Function to show inline success/error message
  window.showInlineSuccess = function(msg, isError = false) {
    let successDiv = document.getElementById('pasteSuccess');
    if (!successDiv) {
      const container = document.getElementById('pasteListingExpanded');
      const newDiv = document.createElement('div');
      newDiv.id = 'pasteSuccess';
      newDiv.className = 'paste-success-message';
      newDiv.style.display = 'none';
      container.parentNode.insertBefore(newDiv, container.nextSibling);
      successDiv = newDiv;
    }
    
    successDiv.innerHTML = `<div style="font-weight:700;font-size:0.9rem;">${msg}</div>`;
    successDiv.style.display = 'block';
    successDiv.style.backgroundColor = isError ? 'rgba(239,68,68,0.12)' : 'rgba(16,185,129,0.12)';
    successDiv.style.borderColor = isError ? '#ef4444' : '#10b981';
    successDiv.style.color = isError ? '#fca5a5' : '#6ee7b7';
    successDiv.style.borderRadius = '8px';
    successDiv.style.padding = '12px 16px';
    successDiv.style.margin = '12px 16px';
    successDiv.style.fontSize = '0.9rem';
    successDiv.style.lineHeight = '1.4';
    
    setTimeout(() => {
      successDiv.style.display = 'none';
      successDiv.innerHTML = '';
    }, 5000);
  };

  // Function to extract listing data from URL
  window.toggleFinanceType = function(type) {
  const financeBtn = document.getElementById('financeTypeBtn');
  const leaseBtn = document.getElementById('leaseTypeBtn');
  const disclaimer = document.getElementById('leaseDisclaimer');
  
  if (financeBtn && leaseBtn) {
    financeBtn.style.display = type === 'finance' ? 'block' : 'none';
    leaseBtn.style.display = type === 'lease' ? 'block' : 'none';
  }
  
  if (disclaimer) {
    disclaimer.style.display = type === 'lease' ? 'block' : 'none';
  }
  
  window.state = window.state || {};
  if (window.state.financeType) {
    window.state.financeType = type;
  }
};

window.extractListing = function() {
  const url = document.getElementById('listingUrlInput').value.trim();
  if (!url) {
    showInlineSuccess('Please paste a listing URL first.', true);
    return;
  }
    
    let listingId = null;
    let idMatch = url.match(/listingId=([0-9]+)/);
    if (idMatch) {
      listingId = idMatch[1];
    } else {
      idMatch = url.match(/details\/(\d+)/);
      if (idMatch) {
        listingId = idMatch[1];
      }
    }
    
    // Mock data - replace with real parser later
    const mockData = {
      brand: 'Toyota',
      model: 'Camry',
      year: '2024',
      price: 28500
    };
    
    // Auto-fill form fields
    const brandSelect = document.getElementById('brand');
    if (brandSelect) {
      brandSelect.value = mockData.brand;
      if (brandSelect.dispatchEvent) {
        brandSelect.dispatchEvent(new Event('change'));
      } else {
        brandSelect.onchange();
      }
    }
    
    const yearSelect = document.getElementById('year');
    if (yearSelect) {
      yearSelect.value = mockData.year;
    }
    
    const dealerPriceInput = document.querySelector('#dealInputs input[type="number"]');
    if (dealerPriceInput) {
      dealerPriceInput.value = mockData.price;
    }
    
    const dealInputs = document.getElementById('dealInputs');
    if (dealInputs) {
      dealInputs.style.display = 'block';
      const placeholder = document.getElementById('dealPlaceholder');
      if (placeholder) {
        placeholder.style.display = 'none';
      }
    }
    
    // Clear input
    document.getElementById('listingUrlInput').value = '';
    
    // Show success message
    const msg = listingId 
      ? '✅ Extracted Listing #' + listingId + '\n' + mockData.brand + ' ' + mockData.model + ' ' + mockData.year + '\nPrice: $' + mockData.price.toLocaleString()
      : '⚠️ Can\'t read this URL yet - filled with best guess.\n' + mockData.brand + ' ' + mockData.model + ' ' + mockData.year + '\nPrice: $' + mockData.price.toLocaleString();
    
    showInlineSuccess(msg);
    
    // Scroll to deal section
    const dealSection = document.getElementById('sec-deal');
    if (dealSection) {
      dealSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  };

  // Hide inline success messages on page load
  window.addEventListener('DOMContentLoaded', function() {
    const successMsg = document.getElementById('pasteSuccess');
    if (successMsg) {
      successMsg.style.display = 'none';
    }
    
    // Initialize finance/lease toggle state
    const financeBtn = document.getElementById('financeTypeBtn');
    const leaseBtn = document.getElementById('leaseTypeBtn');
    const disclaimer = document.getElementById('leaseDisclaimer');
    
    if (financeBtn && leaseBtn && disclaimer) {
      // Default to finance
      financeBtn.style.display = 'block';
      leaseBtn.style.display = 'none';
      disclaimer.style.display = 'none';
      if (!window.state) window.state = {};
      window.state.financeType = 'finance';
    }
  });
})();
