import csv


class FileReader:
    fieldnames = ['count', 'noindex', 'index']
    file_path = 'app/avr_time.csv'
    @classmethod
    def write_data(cls, data_dict):
        with open(cls.file_path, 'w') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=cls.fieldnames)

            writer.writeheader()
            for count, row in data_dict.items():
                row["count"] = count
                writer.writerow(row)
        return True

    @classmethod
    def read_data(cls):
        results = []
        with open(cls.file_path) as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                results.append(row)
        return results