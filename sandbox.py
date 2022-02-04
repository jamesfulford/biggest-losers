rois = []

days = 252
win_rate = .98

for i in range(int(days * win_rate)):
    rois.append(1.01)


for i in range(int(days * (1 - win_rate))):
    rois.append(.9)

current_balance = 1
for roi in rois:
    current_balance *= roi
print(current_balance)
