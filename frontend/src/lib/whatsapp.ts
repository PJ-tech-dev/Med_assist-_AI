export interface EmergencyContact {
  name: string;
  phone: string;
  relationship: string;
  enableWhatsapp: boolean;
  highBpmThreshold: number;
  patientAddress?: string;
}

export const getEmergencyContact = (): EmergencyContact => {
  if (typeof window === 'undefined') {
    return {
      name: 'Primary Contact (Family)',
      phone: '+919876543210',
      relationship: 'Spouse / Next of Kin',
      enableWhatsapp: true,
      highBpmThreshold: 120,
      patientAddress: '',
    };
  }

  const stored = localStorage.getItem('medassist_emergency_contact');
  if (stored) {
    try {
      return JSON.parse(stored);
    } catch {
      // Fallback
    }
  }

  return {
    name: 'Family Emergency Contact',
    phone: '+919876543210',
    relationship: 'Family / Doctor',
    enableWhatsapp: true,
    highBpmThreshold: 120,
    patientAddress: '',
  };
};

export const saveEmergencyContact = (contact: EmergencyContact) => {
  if (typeof window !== 'undefined') {
    localStorage.setItem('medassist_emergency_contact', JSON.stringify(contact));
  }
};

import { api } from '@/lib/api';

export const sendWhatsappAlert = async (alertTitle: string, details: string, lat?: number, lng?: number): Promise<{ success: boolean; phone: string }> => {
  const contact = getEmergencyContact();
  const cleanPhone = contact.phone.replace(/[^0-9+]/g, '');

  const locStr = (lat && lng) ? `${lat}, ${lng}` : "37.7749, -122.4194";

  const mapsUrl = (lat && lng) 
    ? `https://earth.google.com/web/@${lat},${lng},1500d` 
    : "https://earth.google.com/web/@37.7749,-122.4194,1500d";

  const messageText = 
`🚨 *MEDASSIST AI REAL-TIME EMERGENCY ALERT* 🚨

*ALERT TYPE*: ${alertTitle}
*DETAILS*: ${details}
*PATIENT CONTACT*: ${contact.name} (${contact.relationship})
*GPS LOCATION*: ${mapsUrl}

⚠️ *URGENT*: Immediate medical response or check-in is requested!`;

  const encodedText = encodeURIComponent(messageText);
  const whatsappUrl = `whatsapp://send?phone=${cleanPhone.replace('+', '')}&text=${encodedText}`;

  // 2. Open WhatsApp Web / App Client directly BEFORE the async API call to avoid popup blockers
  if (typeof window !== 'undefined' && contact.enableWhatsapp) {
    window.open(whatsappUrl, '_blank', 'noopener,noreferrer');
  }

  // 1. Dispatch Automated Backend API Call to Python FastAPI service silently
  try {
    if (contact.enableWhatsapp) {
      await api.emergency.sendWhatsappAlert({
        phone: cleanPhone,
        contact_name: contact.name,
        emergency_type: alertTitle,
        details: details,
        location: locStr
      });
    }
  } catch (err) {
    console.warn("Automated backend WhatsApp dispatch response:", err);
  }
  
  return {
    success: true,
    phone: contact.phone,
  };
};
