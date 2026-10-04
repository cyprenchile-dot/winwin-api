function updateUI() {
            let totalDaily = 0;
            let totalBox = 0; 
            let totalPrizes = 0;
            let onlineCount = 0;

            let todayStr = getChileDateStr(); 

            machines.forEach(m => {
                let currentSales = m.sales || 0;
                
                if (previousSalesState[m.mac] === undefined) {
                    previousSalesState[m.mac] = currentSales;
                }

                let prevSales = previousSalesState[m.mac];
                let salesDiff = currentSales - prevSales;

                if (salesDiff > 0) {
                    let coinsCount = Math.floor(salesDiff / 100); 
                    for (let i = 0; i < coinsCount; i++) {
                        setTimeout(() => playCoinDropSound(), i * 200); 
                    }
                    triggerGreenPulse(m.mac);
                }
                previousSalesState[m.mac] = currentSales;

                // 1. Contador Físico (Dinero Registrado)
                let cInit = m.coinInitial !== undefined ? m.coinInitial : 3768;
                let telemetryPulses = Math.floor(currentSales / 100);
                let cFinal = (m.coinManualBase !== undefined) ? (m.coinManualBase + telemetryPulses) : (cInit + telemetryPulses);
                
                let cDelta = Math.max(0, cFinal - cInit);
                let dineroRegistrado = cDelta * 100; 
                totalBox += dineroRegistrado;

                // 2. Venta Día (Telemetría) - Sincronización limpia con el backend
                if (!m.dailyLogs) m.dailyLogs = {};
                
                // Si el backend ya mandó un valor para hoy, lo respetamos y actualizamos
                // Si no, aseguramos que la venta de hoy sea el acumulado o la diferencia correcta
                let machineTodaySales = m.dailyLogs[todayStr] !== undefined ? m.dailyLogs[todayStr] : currentSales;
                
                // Si la venta guardada es menor que el cambio total, o si el ESP32 mandó el incremento directo:
                // Nos aseguramos de que refleje los pulsos de hoy.
                m.dailyLogs[todayStr] = machineTodaySales;

                totalDaily += machineTodaySales;

                let isOnline = m.is_online !== false;
                if (isOnline) onlineCount++;
                totalPrizes += (m.prizes || 0);
            });

            rebuildMasterLedgerAndChart(totalDaily);

            let avgPerMachine = machines.length > 0 ? totalDaily / machines.length : 0;
            let avgStatusText = "";
            let avgStatusColor = "";
            let avgBorderColor = "";

            if (avgPerMachine > 15000) {
                avgStatusText = "👑 EXCELENTE (> $15k)";
                avgStatusColor = "#10b981";
                avgBorderColor = "#10b981";
            } else if (avgPerMachine >= 13000) {
                avgStatusText = "⭐ SOBRESALIENTE ($13k - $15k)";
                avgStatusColor = "#34d399";
                avgBorderColor = "#34d399";
            } else if (avgPerMachine >= 11000) {
                avgStatusText = "⚡ MUY BUENO ($11k - $12.9k)";
                avgStatusColor = "#3b82f6";
                avgBorderColor = "#3b82f6";
            } else if (avgPerMachine >= 9000) {
                avgStatusText = "🔹 BUENO ($9k - $10.9k)";
                avgStatusColor = "#60a5fa";
                avgBorderColor = "#60a5fa";
            } else if (avgPerMachine >= 7000) {
                avgStatusText = "⚠️ REGULAR ($7k - $8.9k)";
                avgStatusColor = "#f59e0b";
                avgBorderColor = "#f59e0b";
            } else if (avgPerMachine >= 4000) {
                avgStatusText = "📉 BAJO ($4k - $6.9k)";
                avgStatusColor = "#f97316";
                avgBorderColor = "#f97316";
            } else {
                avgStatusText = "🚨 CRÍTICO (< $4k)";
                avgStatusColor = "#ef4444";
                avgBorderColor = "#ef4444";
            }

            let currentHour = new Date().getHours();
            let operationalHours = Math.max(1, currentHour - 8);
            let cashVelocity = Math.round(totalDaily / operationalHours);

            let totalMachines = machines.length;
            let operationalPercent = totalMachines > 0 ? Math.round((onlineCount / totalMachines) * 100) : 0;

            document.getElementById('daily-sales').innerText = `$${totalDaily.toLocaleString()} CLP`;
            document.getElementById('box-total').innerText = `$${totalBox.toLocaleString()} CLP`;
            document.getElementById('total-prizes').innerText = `${totalPrizes} un.`;
            document.getElementById('active-terminals').innerText = onlineCount;
            document.getElementById('cash-velocity').innerText = `$${cashVelocity.toLocaleString()} / hr`;
            document.getElementById('fleet-operational-percent').innerText = `${operationalPercent}%`;
            document.getElementById('fleet-operational-subtext').innerText = `${onlineCount} de ${totalMachines} online`;
            
            document.getElementById('avg-machine-sales').innerText = `$${Math.round(avgPerMachine).toLocaleString()} CLP`;
            let statusEl = document.getElementById('avg-machine-status');
            if(statusEl) {
                statusEl.innerText = avgStatusText;
                statusEl.style.color = avgStatusColor;
            }
            let cardEl = document.getElementById('avg-performance-card');
            if(cardEl) {
                cardEl.style.borderLeft = `3px solid ${avgBorderColor}`;
            }

            renderMachineBoxes(machines);
            renderLedger();
            renderAuditLog();
            updateFleetMapMarkers(machines);
        }
