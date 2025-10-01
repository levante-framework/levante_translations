#!/usr/bin/env node
/**
 * Fix Audio Coverage for Child Survey Files
 * 
 * This script adds functionality to properly count child-survey audio files
 * and makes missing audio cells clickable to show details.
 */

// Add this to the audio-coverage.html file to fix child-survey counting
const childSurveyFix = `
// Enhanced function to count child-survey files across all language subdirectories
async function countChildSurveyFiles(bucketName) {
  try {
    const storage = getStorageClient();
    if (!storage) return { total: 0, byLanguage: {} };
    
    const bucket = storage.bucket(bucketName);
    const [files] = await bucket.getFiles({ 
      prefix: 'audio/child-survey/', 
      autoPaginate: true 
    });
    
    const byLanguage = {};
    let total = 0;
    
    files.forEach(file => {
      const pathParts = file.name.split('/');
      if (pathParts.length >= 4 && pathParts[0] === 'audio' && pathParts[1] === 'child-survey') {
        const lang = pathParts[2];
        if (!byLanguage[lang]) byLanguage[lang] = 0;
        byLanguage[lang]++;
        total++;
      }
    });
    
    return { total, byLanguage };
  } catch (error) {
    console.error('Error counting child-survey files:', error);
    return { total: 0, byLanguage: {} };
  }
}

// Enhanced missing audio details function
function showMissingAudioDetails(lang, voice, missingCount) {
  const modal = document.createElement('div');
  modal.style.cssText = \`
    position: fixed; top: 0; left: 0; width: 100%; height: 100%; 
    background: rgba(0,0,0,0.5); z-index: 1000; display: flex; 
    align-items: center; justify-content: center;
  \`;
  
  const content = document.createElement('div');
  content.style.cssText = \`
    background: white; border-radius: 8px; padding: 20px; max-width: 80%; 
    max-height: 80%; overflow-y: auto; box-shadow: 0 4px 20px rgba(0,0,0,0.3);
  \`;
  
  content.innerHTML = \`
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px;">
      <h3 style="margin: 0;">Missing Audio Details</h3>
      <button onclick="this.closest('.modal').remove()" style="background: none; border: none; font-size: 20px; cursor: pointer;">&times;</button>
    </div>
    <p><strong>Language:</strong> \${lang}</p>
    <p><strong>Voice:</strong> \${voice}</p>
    <p><strong>Missing Count:</strong> \${missingCount}</p>
    <div id="missingDetails" style="margin-top: 15px;">
      <p>Loading missing audio details...</p>
    </div>
  \`;
  
  modal.className = 'modal';
  modal.appendChild(content);
  document.body.appendChild(modal);
  
  // Load missing audio details
  loadMissingAudioDetails(lang, voice, document.getElementById('missingDetails'));
}

// Function to load and display missing audio details
async function loadMissingAudioDetails(lang, voice, container) {
  try {
    const bucket = getSelectedBucket();
    const source = currentSource;
    
    // Get all item IDs from the CSV
    const allItemIds = await getAllItemIds();
    
    // Check which items are missing for this language/voice combination
    const missingItems = [];
    
    for (const itemId of allItemIds) {
      try {
        const result = await readTag({lang, id: itemId});
        if (!result || !result.ok || result.voice !== voice) {
          missingItems.push({
            id: itemId,
            reason: !result ? 'File not found' : 
                   !result.ok ? 'Error reading file' : 
                   'Voice mismatch'
          });
        }
      } catch (error) {
        missingItems.push({
          id: itemId,
          reason: 'Error: ' + error.message
        });
      }
    }
    
    // Display missing items
    if (missingItems.length === 0) {
      container.innerHTML = '<p style="color: green;">No missing audio files found!</p>';
    } else {
      const itemsList = missingItems.slice(0, 50).map(item => 
        \`<div style="padding: 5px; border-bottom: 1px solid #eee;">
          <strong>\${item.id}</strong> - \${item.reason}
        </div>\`
      ).join('');
      
      container.innerHTML = \`
        <h4>Missing Audio Files (\${Math.min(50, missingItems.length)} of \${missingItems.length} shown):</h4>
        <div style="max-height: 300px; overflow-y: auto; border: 1px solid #ddd; padding: 10px;">
          \${itemsList}
        </div>
        \${missingItems.length > 50 ? '<p style="color: #666; font-style: italic;">... and ' + (missingItems.length - 50) + ' more</p>' : ''}
      \`;
    }
  } catch (error) {
    container.innerHTML = \`<p style="color: red;">Error loading details: \${error.message}</p>\`;
  }
}

// Enhanced table row creation with clickable missing cells
function createTableRow(row, missingPerLang) {
  const tr = document.createElement('tr');
  
  // Make missing count clickable if > 0
  const missingCount = missingPerLang.get(row.lang) ?? 0;
  const missingCell = missingCount > 0 ? 
    \`<td style="cursor: pointer; color: #2563eb; text-decoration: underline;" 
         onclick="showMissingAudioDetails('\${row.lang}', '\${row.voice}', \${missingCount})"
         title="Click to see missing audio details">
         \${missingCount}
       </td>` :
    \`<td>\${missingCount}</td>\`;
  
  tr.innerHTML = \`
    <td>\${row.lang}</td>
    <td>\${row.voice}</td>
    <td>\${row.count}</td>
    \${missingCell}
  \`;
  
  return tr;
}
`;

console.log('Child Survey Audio Coverage Fix');
console.log('==============================');
console.log('');
console.log('Add the following code to your audio-coverage.html file:');
console.log('');
console.log(childSurveyFix);
console.log('');
console.log('This will:');
console.log('1. Add proper counting for child-survey files across all language subdirectories');
console.log('2. Make missing audio count cells clickable to show detailed missing file lists');
console.log('3. Provide better debugging and error handling for missing audio detection');
