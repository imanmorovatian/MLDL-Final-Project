import torch
import torch.nn as nn
import torch.optim as optim
from models.cnn import CNN
from torch.utils.data import ConcatDataset, DataLoader
from torchvision import datasets, transforms
from utils.args import get_parser
from main import set_seed, model_init, get_datasets, gen_clients


def train(data_loader, net, loss_function, optimizer, device):

  samples = 0
  cumulative_loss = 0
  cumulative_accuracy = 0

  net.train()

  for images, targets in data_loader:

    images = images.to(device)
    targets = targets.to(device)

    optimizer.zero_grad()

    # forward
    outputs = net(images)
    loss = loss_function(outputs, targets)

    # backward
    loss.backward()
    optimizer.step()
    
    cumulative_loss += loss.item() * images.shape[0]

    _, predicted = outputs.max(1)
    cumulative_accuracy += predicted.eq(targets).sum().item()

    samples += images.shape[0]

  return cumulative_loss / samples, cumulative_accuracy / samples * 100


def validation_or_test(data_loader, net, loss_function, device):

  samples = 0
  cumulative_loss = 0
  cumulative_accuracy = 0

  net.eval()

  with torch.no_grad():

    for images, targets in data_loader:

      images = images.to(device)
      targets = targets.to(device)

      outputs = net(images)
      loss = loss_function(outputs, targets)
      cumulative_loss += loss.item() * images.shape[0]

      _, predicted = outputs.max(1)
      cumulative_accuracy += predicted.eq(targets).sum().item()

      samples += images.shape[0]

  return cumulative_loss / samples, cumulative_accuracy / samples * 100


DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
EPOCHS = 100
BATCH_SIZE = 64
LEARNING_RATE = 1e-3
MOMENTUM = 0.9
CNN_WEIGHT_DECAY = 1e-5
FC_WEIGHT_DECAY = 1e-3

parser = get_parser()
args = parser.parse_args()
set_seed(args.seed)

model = model_init(args)

print('Generate datasets...')
train_datasets, test_datasets = get_datasets(args)
print('Done.')

if args.dataset == 'femnist':
  train_set = datasets.EMNIST(root='data', split='byclass',train=True, download=True,
                           transform=transforms.Compose([transforms.ToTensor()])
                          )
  
  test_set = datasets.EMNIST(root='data', split='byclass', train=False, download=True,
                          transform=transforms.Compose([transforms.ToTensor()])
                         )
  
elif args.dataset == 'rfemnist':
  train_clients, test_clients = gen_clients(args, train_datasets, test_datasets, model)

  train_set = [client.dataset for client in train_clients]
  test_set = [client.dataset for client in test_clients]

  train_set = ConcatDataset(train_set)
  test_set = ConcatDataset(test_set)

entire_trainset = DataLoader(train_set, shuffle=True)

split_train_size = int(0.8*(len(entire_trainset)))  # use 80% as train set
split_valid_size = len(entire_trainset) - split_train_size  # use 20% as validation set
train_set, val_set = torch.utils.data.random_split(train_set, [split_train_size, split_valid_size]) 

train_loader = DataLoader(train_set, batch_size=BATCH_SIZE, shuffle=True)
val_loader = DataLoader(val_set, batch_size=BATCH_SIZE, shuffle=True)
test_loader = DataLoader(test_set, batch_size=BATCH_SIZE, shuffle=True)

net = CNN().to(DEVICE)
nn.init.xavier_uniform_(net.layer1[0].weight)
nn.init.xavier_uniform_(net.layer2[0].weight)
nn.init.xavier_uniform_(net.fc1[1].weight)
nn.init.xavier_uniform_(net.fc2[1].weight)

loss_function = torch.nn.CrossEntropyLoss()

optimizer = optim.SGD(
    [
        {'params': net.layer1.parameters(), 'weight_decay': CNN_WEIGHT_DECAY},
        {'params': net.layer2.parameters(), 'weight_decay': CNN_WEIGHT_DECAY},
        {'params': net.fc1.parameters(), 'weight_decay': FC_WEIGHT_DECAY},
        {'params': net.fc2.parameters(), 'weight_decay': FC_WEIGHT_DECAY}
    ],
    lr=LEARNING_RATE,
    momentum=MOMENTUM
)


train_losses = []
train_accuracies = []

val_losses = []
val_accuracies = []

for epoch in range(EPOCHS):

  train_loss, train_accuracy = train(train_loader, net, loss_function, optimizer, DEVICE)
  train_losses.append(train_loss)
  train_accuracies.append(train_accuracy)

  val_loss, val_accuracy = validation_or_test(val_loader, net, loss_function, DEVICE)
  val_losses.append(val_loss)
  val_accuracies.append(val_accuracy)


  print(f'Epoch: {epoch+1}/{EPOCHS}')
  print(f'Train Loss: {train_loss:.4f}, Train Accuracy: {train_accuracy:.4f} *** Validation Loss: {val_loss:.4f}, Validation Accuracy: {val_accuracy:.4f}')

test_loss, test_accuracy = validation_or_test(test_loader, net, loss_function, DEVICE)
print(f'Test Loss: {test_loss:.4f}, Test Accuracy: {test_accuracy:.4f}')