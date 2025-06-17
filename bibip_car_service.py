import os
from collections import defaultdict
from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from models import Car, CarFullInfo, CarStatus, Model, ModelSaleStats, Sale


class CarService:
    def __init__(self, base_path: str):
        self.base_path = base_path
        os.makedirs(base_path, exist_ok=True)

        # Создание файлов, если они не существуют
        for file in ["cars.txt", "cars_index.txt",
                     "models.txt", "models_index.txt",
                     "sales.txt", "sales_index.txt"]:
            open(os.path.join(base_path, file), 'a').close()

    # --- Дополнительные методы ---

    def _write_record(self, filename: str, record: str, index_filename: str = None, key: str = None):
        """Запись записи в файл и обновление индекса"""
        record_str = record.ljust(500) + "\n"

        with open(os.path.join(self.base_path, filename), "a+") as f:
            f.seek(0, 2)
            line_num = f.tell() // 501
            f.write(record_str)

        if index_filename and key:
            with open(os.path.join(self.base_path, index_filename), "a+") as f:
                f.write(f"{key};{line_num}\n")
            self._sort_index(index_filename)

    def _sort_index(self, index_filename: str):
        """Сортировка индексного файла"""
        index_file = os.path.join(self.base_path, index_filename)

        with open(index_file, "r") as f:
            lines = sorted(f.readlines(), key=lambda x: x.split(";")[0])

        with open(index_file, "w") as f:
            f.writelines(lines)

    def _get_by_key(self, filename: str, index_filename: str, key: str):
        """Получение записи по ключу через индекс"""
        with open(os.path.join(self.base_path, index_filename), "r") as f:
            for line in f:
                k, line_num = line.strip().split(";")
                if k == key:
                    with open(os.path.join(self.base_path, filename), "r") as data_file:
                        data_file.seek(int(line_num) * 501)
                        return data_file.read(500).strip()
        return None

    def _get_all_records(self, filename: str):
        """Получение всех записей из файла"""
        records = []
        with open(os.path.join(self.base_path, filename), "r") as f:
            while True:
                pos = f.tell()
                line = f.read(500)
                if not line:
                    break
                f.read(1)  # Пропускаю \n
                records.append((pos // 501, line.strip()))
        return records

    def _update_record(self, filename: str, line_num: int, record: str):
        """Обновление записи в файле"""
        record_str = record.ljust(500) + "\n"
        with open(os.path.join(self.base_path, filename), "r+") as f:
            f.seek(line_num * 501)
            f.write(record_str)

    # --- Основные методы ---

    def add_car(self, car: Car) -> None:
        """Добавление автомобиля"""
        record = f"{car.vin};{car.model};{car.price};{car.date_start.strftime('%Y-%m-%d %H:%M:%S')};{car.status}"
        self._write_record("cars.txt", record, "cars_index.txt", car.vin)

    def add_model(self, model: Model) -> None:
        """Добавление модели"""
        record = f"{model.id};{model.name};{model.brand}"
        self._write_record("models.txt", record,
                           "models_index.txt", str(model.id))

    def sell_car(self, sale: Sale) -> None:
        """Продажа автомобиля"""
        # Записываю продажу
        record = f"{sale.sales_number};{sale.car_vin};{sale.cost};{sale.sales_date}"
        self._write_record("sales.txt", record,
                           "sales_index.txt", sale.sales_number)

        # Обновляю статус автомобиля
        car_record = self._get_by_key(
            "cars.txt", "cars_index.txt", sale.car_vin)
        if car_record:
            vin, model, price, date_start, _ = car_record.split(";")
            updated_record = f"{vin};{model};{price};{date_start};{CarStatus.sold}"

            # Нахожу номер строки для обновления
            with open(os.path.join(self.base_path, "cars_index.txt"), "r") as f:
                for line in f:
                    k, line_num = line.strip().split(";")
                    if k == sale.car_vin:
                        self._update_record(
                            "cars.txt", int(line_num), updated_record)
                        break

    def get_cars(self, status: CarStatus) -> List[Car]:
        """Получение списка автомобилей по статусу в порядке их записи (в файл)"""
        cars = []
        for _, record in self._get_all_records("cars.txt"):
            parts = record.split(";")
            if len(parts) == 5:
                car_status = CarStatus(parts[4])
                if car_status == status:
                    cars.append(Car(
                        vin=parts[0],
                        model=int(parts[1]),
                        price=Decimal(parts[2]),
                        date_start=datetime.strptime(
                            parts[3], "%Y-%m-%d %H:%M:%S"),
                        status=car_status
                    ))
        return cars

    def get_car_info(self, vin: str) -> Optional[CarFullInfo]:
        """Получение полной информации об автомобиле"""
        car_record = self._get_by_key("cars.txt", "cars_index.txt", vin)
        if not car_record:
            return None

        vin, model_id, price, date_start, status = car_record.split(";")
        car = Car(
            vin=vin,
            model=int(model_id),
            price=Decimal(price),
            date_start=datetime.strptime(date_start, "%Y-%m-%d %H:%M:%S"),
            status=CarStatus(status)
        )

        # Получаю информацию о модели
        model_record = self._get_by_key(
            "models.txt", "models_index.txt", model_id)
        if not model_record:
            return None

        model_id, model_name, model_brand = model_record.split(";")
        model = Model(id=int(model_id), name=model_name, brand=model_brand)

        # Получаю информацию о продаже
        sales_date = None
        sales_cost = None
        if car.status == CarStatus.sold:
            for _, record in self._get_all_records("sales.txt"):
                parts = record.split(";")
                if len(parts) == 4 and parts[1] == vin:
                    sales_date = datetime.strptime(
                        parts[3], "%Y-%m-%d %H:%M:%S")
                    sales_cost = Decimal(parts[2])
                    break

        return CarFullInfo(
            vin=car.vin,
            car_model_name=model.name,
            car_model_brand=model.brand,
            price=car.price,
            date_start=car.date_start,
            status=car.status,
            sales_date=sales_date,
            sales_cost=sales_cost
        )

    def update_vin(self, old_vin: str, new_vin: str) -> None:
        """Обновление VIN-кода автомобиля"""
        # Получаю текущую запись
        car_record = self._get_by_key("cars.txt", "cars_index.txt", old_vin)
        if not car_record:
            raise ValueError("Car not found")

        _, model, price, date_start, status = car_record.split(";")

        # Удаляю старую запись из индекса
        self._remove_from_index("cars_index.txt", old_vin)

        # Добавляю новую запись
        new_record = f"{new_vin};{model};{price};{date_start};{status}"
        line_num = len(self._get_all_records("cars.txt"))
        self._update_record("cars.txt", line_num, new_record)

        # Обновляю индекс
        with open(os.path.join(self.base_path, "cars_index.txt"), "a") as f:
            f.write(f"{new_vin};{line_num}\n")
        self._sort_index("cars_index.txt")

        # Обновляю ссылки в продажах
        updated_sales = []
        for line_num, record in self._get_all_records("sales.txt"):
            parts = record.split(";")
            if len(parts) == 4 and parts[1] == old_vin:
                updated_record = f"{parts[0]};{new_vin};{parts[2]};{parts[3]}"
                self._update_record("sales.txt", line_num, updated_record)

    def _remove_from_index(self, index_filename: str, key: str):
        """Удаление записи из индекса"""
        index_file = os.path.join(self.base_path, index_filename)

        with open(index_file, "r") as f:
            lines = [line for line in f if not line.startswith(f"{key};")]

        with open(index_file, "w") as f:
            f.writelines(lines)

    def revert_sale(self, sales_number: str) -> None:
        """Отмена продажи"""
        # Получаю информацию о продаже
        sale_record = self._get_by_key(
            "sales.txt", "sales_index.txt", sales_number)
        if not sale_record:
            raise ValueError("Sale not found")

        _, vin, _, _ = sale_record.split(";")

        # Удаляю запись о продаже
        self._remove_from_index("sales_index.txt", sales_number)

        # Статус автомобиля
        car_record = self._get_by_key("cars.txt", "cars_index.txt", vin)
        if car_record:
            vin, model, price, date_start, _ = car_record.split(";")
            updated_record = f"{vin};{model};{price};{date_start};{CarStatus.available}"

            # Нахожу номер строки для обновления
            with open(os.path.join(self.base_path, "cars_index.txt"), "r") as f:
                for line in f:
                    k, line_num = line.strip().split(";")
                    if k == vin:
                        self._update_record(
                            "cars.txt", int(line_num), updated_record)
                        break

    def top_models_by_sales(self) -> List[ModelSaleStats]:
        model_counts = defaultdict(int)
        model_prices = defaultdict(list)

        # Собираю статистику по моделям
        for _, record in self._get_all_records("sales.txt"):
            parts = record.split(";")
            if len(parts) == 4:
                vin = parts[1]
                price = Decimal(parts[2])
                car_record = self._get_by_key(
                    "cars.txt", "cars_index.txt", vin)
                if car_record:
                    model_id = int(car_record.split(";")[1])
                    model_counts[model_id] += 1
                    model_prices[model_id].append(price)

        # Средняя цена
        avg_prices = {mid: sum(prices)/len(prices)
                      for mid, prices in model_prices.items()}

        models_info = {}
        for _, record in self._get_all_records("models.txt"):
            model_id, name, brand = record.split(";")
            models_info[int(model_id)] = (name, brand)

        # Сортирую по количеству продаж (убывание), по средней цене (убывание)
        sorted_models = sorted(
            model_counts.items(),
            key=lambda x: (-x[1], -avg_prices[x[0]])
        )

        result = []
        for model_id, count in sorted_models[:3]:
            name, brand = models_info.get(model_id, ("Unknown", "Unknown"))
            result.append(ModelSaleStats(
                car_model_name=name,
                brand=brand,
                sales_number=count
            ))

        return result
