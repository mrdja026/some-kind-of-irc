export function queueAndSendGameJoin(
  channelId: number,
  pendingChannels: Set<number>,
  socket: WebSocket | null,
): void {
  if (!channelId || channelId <= 0) {
    return
  }

  pendingChannels.add(channelId)

  if (socket && socket.readyState === WebSocket.OPEN) {
    socket.send(
      JSON.stringify({
        type: 'game_join',
        channel_id: channelId,
      }),
    )
  }
}
