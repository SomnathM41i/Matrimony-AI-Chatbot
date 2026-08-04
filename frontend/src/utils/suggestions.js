export const SUGGESTION_HINTS = {
  'मागील सर्च चालू ठेवा': 'Continue previous search',
  'पुढील प्रोफाइल दाखवा': 'Show next profile',
  'नवीन सर्च सुरू करा': 'Start a new search',
  'माझ्या पसंतीनुसार नवीन सर्च': 'New search with my preferences',
  'माझ्या पसंतीनुसार प्रोफाइल दाखवा': 'Show profiles matching my preferences',
  'आणखी दोन प्रोफाइलची तुलना करा': 'Compare two more profiles',
  'आधी पाहिलेले प्रोफाइल पुन्हा पाहा': 'View profiles seen earlier',
  'मला Matri ID जोडायचा आहे': 'I want to add my Matri ID',
  'पुण्यातील 5 मुलींची प्रोफाइल दाखवा': 'Show 5 brides from Pune',
  'मुंबईतील मुलांची प्रोफाइल दाखवा': 'Show grooms from Mumbai',
  'माझ्या जोडीदाराच्या पसंती सांगा': 'Tell my partner preferences',
  'success stories दाखवा': 'Show success stories',
}

export function suggestionHint(text) {
  return SUGGESTION_HINTS[text] || ''
}
