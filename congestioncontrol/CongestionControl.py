class CongestionControl:
    def __init__(self, MSS: int):
        self.MSS = MSS
        # cwnd se mantiene como float internamente para no perder las fracciones
        # en congestion avoidance, pero se entrega como int cuando se solicita.
        self.cwnd = float(MSS)
        self.ssthresh = None
        self.current_state = "slow_start"

    def get_cwnd(self) -> int:
        """Retorna el valor actual del tamaño de la ventana de congestión en bytes."""
        return int(self.cwnd)

    def get_MSS_in_cwnd(self) -> int:
        """Retorna la cantidad de MSS completos que caben en la ventana de congestión."""
        return self.get_cwnd() // self.MSS

    def event_ack_received(self):
        """Maneja el comportamiento del tamaño de ventana al recibir un ACK exitoso."""
        if self.current_state == "slow_start":
            self.cwnd += self.MSS
            
            # Si se supera el threshold, pasamos a congestion avoidance.
            if self.ssthresh is not None and self.cwnd >= self.ssthresh:
                self.current_state = "congestion_avoidance"
                
        elif self.current_state == "congestion_avoidance":
            # En AIMD, se suma una fracción de MSS. Al recibir suficientes ACKs
            # equivalentes a 1 MSS, el cwnd habrá aumentado en total 1 MSS.
            MSS_in_cwnd = self.get_MSS_in_cwnd()
            if MSS_in_cwnd > 0: # Evitar división por cero por precaución
                self.cwnd += self.MSS / MSS_in_cwnd

    def event_timeout(self):
        """Maneja el evento de pérdida por timeout (Multiplicative Decrease)."""
        self.ssthresh = int(self.cwnd / 2)
        self.cwnd = float(self.MSS)
        self.current_state = "slow_start"

    def is_state_slow_start(self) -> bool:
        """Retorna True si el estado actual es slow start."""
        return self.current_state == "slow_start"

    def is_state_congestion_avoidance(self) -> bool:
        """Retorna True si el estado actual es congestion avoidance."""
        return self.current_state == "congestion_avoidance"

    def get_ssthresh(self):
        """Retorna el umbral ssthresh actual (None si aún no ocurre el primer timeout)."""
        return self.ssthresh