import type { WhatsAppChannelRead } from "@/src/types/api";

export function ChannelBadge({
  channel
}: {
  channel: Pick<WhatsAppChannelRead, "name" | "display_phone_number" | "color_hex">;
}) {
  return (
    <span className="channel-badge" style={{ ["--channel-color" as string]: channel.color_hex }}>
      <span className="channel-badge__dot" />
      <span>{channel.name}</span>
      <small>{channel.display_phone_number}</small>
    </span>
  );
}
