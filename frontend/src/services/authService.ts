import {
  createNestablePublicClientApplication,
  type IPublicClientApplication,
} from '@azure/msal-browser';

/**
 * Infrastruktur-Service: Kapselt Nested App Authentication (NAA) für den
 * Microsoft-Graph-Zugriff des Aufgabenradars.
 *
 * Erfordert eine Azure-AD/Entra-ID-App-Registrierung (Delegated Permission
 * `Mail.Read`), deren Client-ID über VITE_AAD_CLIENT_ID gesetzt wird
 * (siehe .env.example und README).
 */
const CLIENT_ID = import.meta.env.VITE_AAD_CLIENT_ID as string | undefined;
// Bei einer "Single tenant"-App-Registrierung (empfohlen für Hochschulkonten)
// muss hier die Tenant-ID stehen statt "common" — siehe README "Graph-API-Setup".
const TENANT_ID = (import.meta.env.VITE_AAD_TENANT_ID as string | undefined) || 'common';
const GRAPH_MAIL_READ_SCOPES = ['Mail.Read'];

let clientPromise: Promise<IPublicClientApplication> | null = null;

function getClient(): Promise<IPublicClientApplication> {
  if (!CLIENT_ID) {
    throw new Error(
      'VITE_AAD_CLIENT_ID ist nicht gesetzt. Für den Postfach-Scan wird eine Azure-AD-App-Registrierung benötigt (siehe README).'
    );
  }

  if (!clientPromise) {
    clientPromise = createNestablePublicClientApplication({
      auth: {
        clientId: CLIENT_ID,
        authority: `https://login.microsoftonline.com/${TENANT_ID}`,
        supportsNestedAppAuth: true,
      },
    });
  }

  return clientPromise;
}

/**
 * Holt ein Access Token für Microsoft Graph (Mail.Read). Versucht zuerst
 * stillen SSO-Abgleich über den Outlook-Host, fällt auf ein Login-Popup
 * zurück, falls noch keine Zustimmung vorliegt.
 */
export async function getGraphAccessToken(): Promise<string> {
  const client = await getClient();
  const request = { scopes: GRAPH_MAIL_READ_SCOPES };

  try {
    const result = await client.acquireTokenSilent(request);
    return result.accessToken;
  } catch {
    const result = await client.acquireTokenPopup(request);
    return result.accessToken;
  }
}
