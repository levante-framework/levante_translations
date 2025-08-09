function toggleValidationPanel() {
    const header = document.querySelector('.validation-header');
    const content = document.getElementById('validationContent');
    header.classList.toggle('collapsed');
    content.classList.toggle('expanded');
}

function validateSelected() {
    const credentials = getCredentials();
    if (!credentials.googleTranslateApiKey) {
        alert('Please add your Google Translate API key in the credentials manager.');
        return;
    }
    const selectedRows = document.querySelectorAll('.data-row.selected');
    if (selectedRows.length === 0) {
        alert('Please select one or more translations to validate.');
        return;
    }
    selectedRows.forEach(row => {
        const validateBtn = row.querySelector('.validate-btn');
        if (validateBtn && validateBtn.onclick) validateBtn.click();
    });
}

function validateAll() {
    const credentials = getCredentials();
    if (!credentials.googleTranslateApiKey) {
        alert('Please add your Google Translate API key in the credentials manager.');
        return;
    }
    const currentLanguage = window.dashboard?.currentLanguage;
    if (!currentLanguage) {
        alert('No active language found.');
        return;
    }
    const currentTable = document.getElementById(`table-${currentLanguage}`);
    if (!currentTable) {
        alert(`Current language table not found: table-${currentLanguage}`);
        return;
    }
    const validateBtns = currentTable.querySelectorAll('.validate-btn');
    if (validateBtns.length === 0) {
        alert('No translations available to validate in the current language.');
        return;
    }
    if (confirm(`This will validate ${validateBtns.length} ${currentLanguage.toUpperCase()} translations. This may take some time. Continue?`)) {
        let currentIndex = 0;
        const validateNext = () => {
            if (currentIndex < validateBtns.length) {
                const btn = validateBtns[currentIndex];
                if (btn && !btn.disabled) btn.click();
                currentIndex++;
                setTimeout(validateNext, 1000);
            }
        };
        validateNext();
    }
}

function saveValidationsManually() {
    const result = window.dashboard.saveValidationResults();
    const button = document.getElementById('saveValidations');
    const originalText = button.innerHTML;
    if (result.success) {
        button.innerHTML = '<i class="fas fa-check"></i> Saved!';
        button.disabled = true;
        window.dashboard.setStatus(`💾 Saved ${result.itemCount} items (${result.validationCount} validations) to browser storage & shared team storage`, 'success');
        setTimeout(() => { button.innerHTML = originalText; button.disabled = false; }, 2000);
    } else {
        button.innerHTML = '<i class="fas fa-exclamation-triangle"></i> Error!';
        button.disabled = true;
        window.dashboard.setStatus(`❌ Error saving validations: ${result.error}`, 'error');
        setTimeout(() => { button.innerHTML = originalText; button.disabled = false; }, 3000);
    }
}

async function loadValidationsFromShared() {
    const button = document.getElementById('loadValidations');
    const originalText = button.innerHTML;
    try {
        button.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Loading...';
        button.disabled = true;
        const success = await window.dashboard.loadFromSharedStorage();
        if (success) {
            window.dashboard.applyStoredValidationResultsForCurrentLanguage();
            button.innerHTML = '<i class="fas fa-check"></i> Loaded!';
            window.dashboard.setStatus('🌐 Successfully loaded validation results from shared session storage', 'success');
            setTimeout(() => { button.innerHTML = originalText; button.disabled = false; }, 2000);
        } else {
            button.innerHTML = '<i class="fas fa-exclamation-triangle"></i> No Data';
            window.dashboard.setStatus('⚠️ No shared validation data found', 'warning');
            setTimeout(() => { button.innerHTML = originalText; button.disabled = false; }, 2000);
        }
    } catch (error) {
        button.innerHTML = '<i class="fas fa-exclamation-triangle"></i> Error!';
        window.dashboard.setStatus(`❌ Error loading shared validations: ${error.message}`, 'error');
        setTimeout(() => { button.innerHTML = originalText; button.disabled = false; }, 3000);
    }
}

function exportValidationsToJSONFile() {
    let totalValidations = 0;
    Object.keys(window.dashboard.validation_results).forEach(itemId => { totalValidations += Object.keys(window.dashboard.validation_results[itemId]).length; });
    const exportData = {
        metadata: {
            exported_at: new Date().toISOString(),
            exported_by: 'Levante Translation Dashboard',
            version: '1.0',
            total_items: Object.keys(window.dashboard.validation_results).length,
            total_validations: totalValidations,
            languages: Object.keys(window.dashboard.languages)
        },
        validation_results: window.dashboard.validation_results
    };
    const dataStr = JSON.stringify(exportData, null, 2);
    const dataUri = 'data:application/json;charset=utf-8,' + encodeURIComponent(dataStr);
    const linkElement = document.createElement('a');
    linkElement.setAttribute('href', dataUri);
    linkElement.setAttribute('download', 'validation_results.json');
    linkElement.click();
}

function updateValidationSummary() {
    const currentLanguage = window.dashboard?.currentLanguage;
    if (!currentLanguage) return;
    const currentTable = document.getElementById(`table-${currentLanguage}`);
    if (!currentTable) return;
    const indicators = currentTable.querySelectorAll('.status-indicator');
    let good = 0, warning = 0, error = 0, pending = 0;
    indicators.forEach(indicator => {
        if (indicator.classList.contains('status-good')) good++;
        else if (indicator.classList.contains('status-warning')) warning++;
        else if (indicator.classList.contains('status-error')) error++;
        else pending++;
    });
    document.getElementById('goodCount').textContent = good;
    document.getElementById('warningCount').textContent = warning;
    document.getElementById('errorCount').textContent = error;
    document.getElementById('pendingCount').textContent = pending;
}
