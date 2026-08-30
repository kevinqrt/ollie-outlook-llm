import { getGraphAccessToken } from './authService';

export interface UnreadMessage {
  id: string;
  subject: string;
  from: string;
  bodyText: string;
  links: string[];
  webLink: string;
}

const GRAPH_BASE = 'https://graph.microsoft.com/v1.0';

interface GraphMessage {
  id: string;
  subject?: string;
  from?: { emailAddress?: { name?: string; address?: string } };
  body?: { content?: string };
  webLink?: string;
}

interface GraphMessageListResponse {
  value: GraphMessage[];
}

function extractLinks(html: string): string[] {
  const hrefPattern = /href=["']([^"']+)["']/gi;
  const links: string[] = [];
  let match = hrefPattern.exec(html);
  while (match !== null) {
    const url = match[1];
    if (/^https?:\/\//i.test(url) && !links.includes(url)) {
      links.push(url);
    }
    match = hrefPattern.exec(html);
  }
  return links;
}

function stripHtml(html: string): string {
  return html
    .replace(/<style[\s\S]*?<\/style>/gi, '')
    .replace(/<script[\s\S]*?<\/script>/gi, '')
    .replace(/<[^>]+>/g, ' ')
    .replace(/&nbsp;/gi, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

/**
 * Holt alle ungelesenen Mails aus dem Posteingang über Microsoft Graph.
 * Der Body wird als HTML angefragt, damit Links (hrefs) erhalten bleiben,
 * bevor der Text fürs LLM auf reinen Fließtext reduziert wird.
 */
export async function fetchUnreadMessages(
  limit = 25
): Promise<UnreadMessage[]> {
  const token = await getGraphAccessToken();

  const url =
    `${GRAPH_BASE}/me/mailFolders/Inbox/messages` +
    `?$filter=isRead eq false&$top=${limit}&$select=id,subject,from,body,webLink`;

  const response = await fetch(url, {
    headers: { Authorization: `Bearer ${token}` },
  });

  if (!response.ok) {
    throw new Error(
      `Graph-Anfrage fehlgeschlagen: ${response.status} ${response.statusText}`
    );
  }

  const data = (await response.json()) as GraphMessageListResponse;

  return data.value.map((msg) => {
    const html = msg.body?.content ?? '';
    return {
      id: msg.id,
      subject: msg.subject || '(kein Betreff)',
      from:
        msg.from?.emailAddress?.name ||
        msg.from?.emailAddress?.address ||
        'Unbekannt',
      bodyText: stripHtml(html),
      links: extractLinks(html),
      webLink: msg.webLink ?? '',
    };
  });
}
