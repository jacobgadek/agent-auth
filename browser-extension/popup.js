document.addEventListener('DOMContentLoaded', function() {
  const domainEl = document.getElementById('domain');
  const outputEl = document.getElementById('output');
  const exportBtn = document.getElementById('export');
  const copyBtn = document.getElementById('copy');
  const successEl = document.getElementById('success');
  
  let currentDomain = '';
  let cookiesJson = '';
  
  // Get current tab's domain
  chrome.tabs.query({active: true, currentWindow: true}, function(tabs) {
    if (tabs[0]) {
      const url = new URL(tabs[0].url);
      currentDomain = url.hostname;
      domainEl.textContent = currentDomain;
    }
  });
  
  // Export cookies
  exportBtn.addEventListener('click', function() {
    chrome.cookies.getAll({domain: currentDomain}, function(cookies) {
      const cookieObj = {};
      cookies.forEach(cookie => {
        cookieObj[cookie.name] = cookie.value;
      });
      
      cookiesJson = JSON.stringify(cookieObj, null, 2);
      outputEl.textContent = cookiesJson;
      outputEl.style.display = 'block';
      copyBtn.style.display = 'block';
    });
  });
  
  // Copy to clipboard
  copyBtn.addEventListener('click', function() {
    navigator.clipboard.writeText(cookiesJson).then(function() {
      successEl.style.display = 'block';
      setTimeout(() => {
        successEl.style.display = 'none';
      }, 3000);
    });
  });
});
